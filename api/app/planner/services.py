"""Use cases coordinate scoped storage; model calls never write business records."""
import hashlib
import json
from datetime import date, timedelta
from .domain import Conflict, check_conflicts, course_occurrences, next_review, normalize_answer, today
from .repository import RecordStore
from .schemas import Course, Task, Word, Run, Settings, Plan

MODELS = {'tasks': ('task', Task), 'courses': ('course', Course), 'words': ('word', Word), 'runs': ('run', Run)}


def settings(store):
    values = store.list('settings')
    return values[0] if values else {**Settings().model_dump(mode='json'), 'id': None, 'version': 0}


def snapshot(store):
    values = sorted((kind, r['id'], r['version']) for kind in ('course', 'task', 'settings', 'run') for r in store.list(kind))
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def occupied(store, start, end):
    return course_occurrences(store.list('course'), start, end) + [t for t in store.list('task') if start <= t['date'] <= end and t['status'] != 'skipped']


def save_resource(store: RecordStore, resource, value, key=None, version=None):
    kind, model = MODELS[resource]
    old = store.get(kind, key) if key else None
    # Hidden form fields and newly added optional fields must survive old clients.
    preserved = ('status', 'discomfort', 'training_type') if kind == 'run' else ('phonetic_uk',) if kind == 'word' else ()
    data = model.model_validate({**{k: old[k] for k in preserved if old and k in old}, **value}).model_dump(mode='json')
    if kind == 'task':
        check_conflicts([dict(data, id=key)], occupied(store, data['date'], data['date']))
        if old and any(r.get('task_id') == key for r in store.list('run')) and (data['date'] != old['date'] or data['category'] != 'training'):
            raise Conflict('该任务已关联训练记录，请先解除关联再修改日期或类别')
    if kind == 'course':
        first = date.fromisoformat(data['semester_start'])
        first -= timedelta(days=first.weekday())
        end = first + timedelta(weeks=data['end_week'])
        occurrences = course_occurrences([dict(data, id=key)], first.isoformat(), end.isoformat())
        check_conflicts(occurrences, occupied(store, first.isoformat(), end.isoformat()))
    if kind == 'word':
        duplicates = [w for w in store.list(kind) if normalize_answer(w['term']) == normalize_answer(data['term']) and w['id'] != key]
        if duplicates:
            raise Conflict('这个词已在词汇表中，请编辑原词条补充词义或例句')
        data.update({k: old[k] for k in ('stage', 'review_on', 'wrong_count') if old and k in old})
        data.setdefault('stage', 0)
        data.setdefault('review_on', today())
        data.setdefault('wrong_count', 0)
    if kind == 'run' and old and old.get('task_id') and old['task_id'] != data['task_id']:
        previous = store.get('task', old['task_id'])
        store.save('task', {**previous, 'status': 'pending'}, previous['id'], previous['version'])
    if kind == 'run' and data['task_id']:
        task = store.get('task', data['task_id'])
        if task['category'] != 'training' or task['date'] != data['date']:
            raise Conflict('请选择同一天的训练任务')
        if any(r.get('task_id') == data['task_id'] and r['id'] != key for r in store.list('run')):
            raise Conflict('该训练已有记录，请编辑已有记录')
        store.save('task', {**task, 'status': data['status']}, task['id'], task['version'])
    result = store.save(kind, data, key, version)
    label = {'task': '待办', 'course': '课程', 'word': '词汇', 'run': '训练'}[kind]
    action = '修改' if old else '添加'
    if kind == 'task' and old and old['status'] != data['status']:
        action = {'done': '完成', 'pending': '恢复待办', 'partial': '部分完成', 'skipped': '跳过'}[data['status']]
    if kind != 'word':
        store.event(action, {'title': data.get('title') or data.get('term') or f"跑步 {data.get('distance_km', 0)} km", 'resource': label, 'record_id': result['id']}, data.get('date'))
    return result


def apply_plan(store, draft_id, version):
    draft = store.get('draft', draft_id)
    if draft.get('rejected'):
        raise Conflict('这份草稿已否决，不能采用')
    if draft.get('applied'):
        return draft
    if draft['version'] != version or draft['snapshot'] != snapshot(store):
        raise Conflict('课表或任务在草稿生成后发生变化，请重新生成计划')
    plan = Plan.model_validate(draft['plan']).model_dump(mode='json')
    start, end = draft['week_start'], (date.fromisoformat(draft['week_start']) + timedelta(days=6)).isoformat()
    if any(not start <= t['date'] <= end for t in plan['tasks']):
        raise Conflict('计划中的任务日期必须位于当前周')
    check_conflicts(plan['tasks'], occupied(store, start, end))
    for task in plan['tasks']:
        store.save('task', {**task, 'status': 'pending', 'source_id': draft_id})
    result = store.save('draft', {**draft, 'applied': True}, draft_id, version)
    store.event('采用计划', {'title': plan['summary'][:160], 'count': len(plan['tasks'])})
    return result


def editable_plan(store, draft_id, version):
    draft = store.get('draft', draft_id)
    if draft['version'] != version:
        raise Conflict('草稿已更新，请刷新后重试')
    if draft.get('applied') or draft.get('rejected'):
        raise Conflict('已采用或否决的草稿不能修改')
    return draft


def validate_plan(store, plan, start):
    Plan.model_validate(plan)
    end = (date.fromisoformat(start) + timedelta(days=6)).isoformat()
    if any(not start <= t['date'] <= end for t in plan['tasks']):
        raise Conflict('计划中的任务日期必须位于当前周')
    check_conflicts(plan['tasks'], occupied(store, start, end))


def training_history(store, start):
    """Three complete Monday–Sunday weeks preceding the target week, by run date."""
    target = date.fromisoformat(start)
    first = target - timedelta(weeks=3)
    runs = sorted((r for r in store.list('run') if first.isoformat() <= r['date'] < start), key=lambda r: (r['date'], r['id']))
    weeks = []
    for n in range(3):
        left = first + timedelta(weeks=n)
        right = left + timedelta(days=6)
        rows = [r for r in runs if left.isoformat() <= r['date'] <= right.isoformat()]
        actual = [r for r in rows if r['status'] != 'skipped']
        types = {}
        for r in actual:
            name = r.get('training_type') or 'unclassified'
            types[name] = types.get(name, 0) + 1
        weeks.append({'start': left.isoformat(), 'end': right.isoformat(), 'data_missing': not rows,
                      'count': len(actual), 'skipped_count': len(rows) - len(actual),
                      'distance_km': round(sum(r['distance_km'] for r in actual), 2),
                      'duration_minutes': round(sum(r['duration_minutes'] for r in actual), 2),
                      'training_types': types, 'average_effort': round(sum(r['effort'] for r in actual) / len(actual), 2) if actual else None})
    return {'start': first.isoformat(), 'end': (target - timedelta(days=1)).isoformat(), 'runs': runs, 'weeks': weeks}


def apply_course_draft(store, draft_id, version):
    draft = store.get('course_draft', draft_id)
    if draft.get('applied'):
        return draft
    if draft['version'] != version:
        raise Conflict('课表草稿已更新，请刷新')
    if not draft['courses']:
        raise ValueError('请至少填写一门课程')
    for value in draft['courses']:
        save_resource(store, 'courses', value)
    result = store.save('course_draft', {**draft, 'applied': True}, draft_id, version)
    store.event('导入课表', {'title': f"导入 {len(draft['courses'])} 门课程"})
    return result


def review_word(store, word_id, correct):
    word = store.get('word', word_id)
    stage, due = next_review(word['stage'], correct, today())
    store.save('word', {**word, 'stage': stage, 'review_on': due, 'wrong_count': word['wrong_count'] + int(not correct)}, word_id, word['version'])
    if not any(w['review_on'] <= today() for w in store.list('word')):
        for task in store.list('task'):
            if task['date'] == today() and task['category'] == 'vocabulary' and task['status'] == 'pending':
                store.save('task', {**task, 'status': 'done'}, task['id'], task['version'])
                store.event('完成', {'title': task['title'], 'record_id': task['id']})


def submit_answer(store, question_id, answer):
    question = store.get('question', question_id)
    if question.get('attempt'):
        raise Conflict('这道题已作答，请开始一组新练习')
    attempt = store.save('attempt', {'question_id': question_id, 'word_id': question['word_id'], 'answer': answer, 'date': today(), 'mode': question['mode'], 'status': 'pending' if question['mode'] == 'translation' else 'graded', 'correct': None, 'feedback': ''})
    store.save('question', {**question, 'attempt': attempt['id']}, question_id, question['version'])
    if question['mode'] != 'translation':
        correct = normalize_answer(answer) == normalize_answer(question['expected'])
        attempt = store.save('attempt', {**attempt, 'correct': correct, 'feedback': question['explanation'] or ('回答正确' if correct else '查看参考答案后再试')}, attempt['id'], attempt['version'])
        review_word(store, question['word_id'], correct)
        store.event('词汇练习', {'title': store.get('word', question['word_id'])['term'], 'correct': correct})
    return {**attempt, 'expected': question['expected']}
