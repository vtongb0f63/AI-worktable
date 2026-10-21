import csv
import io
import json
from datetime import date, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, File, UploadFile, Query, HTTPException
from pydantic import ValidationError
from ..security import require_user
from .. import config
from . import schemas, services, jobs
from .repository import records
from .domain import today, week_start, course_occurrences, Conflict

router = APIRouter(prefix='/api/v1', tags=['personal planner'])
Resource = Literal['tasks', 'courses', 'words', 'runs']


@router.get('/overview')
def overview(day: date | None = None, user=Depends(require_user)):
    target = day.isoformat() if day else today()
    with records(user['id']) as store:
        return {'date': target, 'tasks': sorted([t for t in store.list('task') if t['date'] == target], key=lambda t: t.get('start_time') or '99:99'), 'courses': course_occurrences(store.list('course'), target, target), 'due_words': sum(w['review_on'] <= target for w in store.list('word')), 'runs': [r for r in store.list('run') if r['date'] == target], 'news': [r for r in store.list('news') if r['date'] == target][:12]}


@router.get('/settings')
def get_settings(user=Depends(require_user)):
    with records(user['id']) as store:
        return services.settings(store)


@router.put('/settings')
def put_settings(value: schemas.Revision, user=Depends(require_user)):
    data = schemas.Settings.model_validate(value.data).model_dump(mode='json')
    with records(user['id']) as store:
        old = services.settings(store)
        return store.save('settings', data, old['id'], value.version if old['id'] else None)


@router.get('/calendar')
def calendar(start: date, end: date, user=Depends(require_user)):
    if not 0 <= (end - start).days <= 62:
        raise ValueError('日历查询范围须在 0–62 天内')
    with records(user['id']) as store:
        return {'courses': course_occurrences(store.list('course'), start.isoformat(), end.isoformat()), 'tasks': [t for t in store.list('task') if start.isoformat() <= t['date'] <= end.isoformat()]}


@router.get('/records/{resource}')
def list_records(resource: Resource, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), q: str = '', filter: Literal['all', 'due', 'wrong'] = 'all', user=Depends(require_user)):
    with records(user['id']) as store:
        rows = store.list(services.MODELS[resource][0])
        if q:
            rows = [r for r in rows if q.casefold() in json.dumps(r, ensure_ascii=False).casefold()]
        if resource == 'words' and filter != 'all':
            rows = [r for r in rows if (r['review_on'] <= today() if filter == 'due' else r['wrong_count'] > 0)]
        return {'items': rows[offset:offset + limit], 'total': len(rows)}


@router.get('/running-summary')
def running_summary(start: date, user=Depends(require_user)):
    end = start + timedelta(days=6)
    with records(user['id']) as store:
        return {'runs': [r for r in store.list('run') if start.isoformat() <= r['date'] <= end.isoformat()], 'tasks': [t for t in store.list('task') if t['category'] == 'training' and start.isoformat() <= t['date'] <= end.isoformat()]}


@router.post('/records/tasks', status_code=201)
def add_task(value: schemas.Task, user=Depends(require_user)):
    with records(user['id']) as store:
        return services.save_resource(store, 'tasks', value.model_dump(mode='json'))


@router.post('/records/courses', status_code=201)
def add_course(value: schemas.Course, user=Depends(require_user)):
    with records(user['id']) as store:
        return services.save_resource(store, 'courses', value.model_dump(mode='json'))


@router.post('/records/words', status_code=201)
def add_word(value: schemas.Word, user=Depends(require_user)):
    with records(user['id']) as store:
        return services.save_resource(store, 'words', value.model_dump(mode='json'))


@router.post('/records/runs', status_code=201)
def add_run(value: schemas.Run, user=Depends(require_user)):
    with records(user['id']) as store:
        return services.save_resource(store, 'runs', value.model_dump(mode='json'))


@router.put('/records/{resource}/{key}')
def edit_record(resource: Resource, key: str, value: schemas.Revision, user=Depends(require_user)):
    with records(user['id']) as store:
        return services.save_resource(store, resource, value.data, key, value.version)


@router.delete('/records/{resource}/{key}', status_code=204)
def delete_record(resource: Resource, key: str, version: int, user=Depends(require_user)):
    with records(user['id']) as store:
        kind = services.MODELS[resource][0]
        before = store.get(kind, key)
        if kind == 'task' and any(r.get('task_id') == key for r in store.list('run')):
            raise Conflict('请先解除训练记录与该任务的关联')
        if kind == 'word' and any(q.get('word_id') == key for q in store.list('question')):
            raise Conflict('这个单词已有练习记录，请保留词条以便查阅，也可以编辑其内容')
        if kind == 'run' and before.get('task_id'):
            task = store.get('task', before['task_id'])
            store.save('task', {**task, 'status': 'pending'}, task['id'], task['version'])
        store.delete(kind, key, version)
        store.event('删除', {'title': before.get('title') or before.get('term') or '训练记录'})


@router.post('/words/import', status_code=201)
async def import_words(file: UploadFile = File(), user=Depends(require_user)):
    raw = await file.read(500001)
    if len(raw) > 500000:
        raise ValueError('CSV 文件不能超过 500 KB')
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    if not rows or len(rows) > 1000:
        raise ValueError('请导入 1–1000 行，列名使用 term,meaning,example,tags')
    count, skipped = 0, 0
    with records(user['id']) as store:
        for row in rows:
            try:
                services.save_resource(store, 'words', row)
                count += 1
            except Conflict:
                skipped += 1
    return {'imported': count, 'skipped': skipped}


@router.post('/words/{key}/review')
def word_review(key: str, value: schemas.Review, user=Depends(require_user)):
    with records(user['id']) as store:
        services.review_word(store, key, value.correct)
        return store.get('word', key)


@router.get('/journal')
def journal(day: date, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), user=Depends(require_user)):
    with records(user['id']) as store:
        events = [r for r in store.list('journal_event') if r['date'] == day.isoformat()]
        return {'items': events[offset:offset + limit], 'total': len(events), 'notes': [r for r in store.list('journal_note') if r['date'] == day.isoformat()]}


@router.post('/journal', status_code=201)
def add_journal(value: schemas.Journal, user=Depends(require_user)):
    with records(user['id']) as store:
        return store.save('journal_note', value.model_dump(mode='json'))


@router.get('/news')
def news(day: date | None = None, category: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100), user=Depends(require_user)):
    with records(user['id']) as store:
        rows = store.list('news')
        if day:
            rows = [r for r in rows if r['date'] == day.isoformat()]
        if category:
            rows = [r for r in rows if r['category'] == category]
        return {'items': rows[offset:offset + limit], 'total': len(rows), 'editions': store.list('edition')[:30]}


@router.post('/news/{key}/bookmark')
def bookmark(key: str, user=Depends(require_user)):
    with records(user['id']) as store:
        item = store.get('news', key)
        return store.save('news', {**item, 'bookmarked': not item.get('bookmarked', False)}, key, item['version'])


@router.get('/drafts')
def drafts(user=Depends(require_user)):
    with records(user['id']) as store:
        return {'plans': store.list('draft')[:30], 'courses': store.list('course_draft')[:10]}


@router.put('/drafts/{kind}/{key}')
def edit_draft(kind: Literal['plan', 'course'], key: str, value: schemas.Revision, user=Depends(require_user)):
    with records(user['id']) as store:
        name = 'draft' if kind == 'plan' else 'course_draft'
        old = store.get(name, key)
        if old.get('applied'):
            raise Conflict('已采用的草稿不能再次修改')
        if kind == 'plan':
            data = {'plan': schemas.Plan.model_validate(value.data).model_dump(mode='json')}
        else:
            raw = value.data.get('courses', [])
            if len(raw) > 100:
                raise ValueError('课程过多')
            data = {'courses': [schemas.Course.model_validate(c).model_dump(mode='json') for c in raw]}
        return store.save(name, {**old, **data}, key, value.version)


@router.post('/drafts/{kind}/{key}/adoption')
def adopt(kind: Literal['plan', 'course'], key: str, value: schemas.Revision, user=Depends(require_user)):
    with records(user['id']) as store:
        return (services.apply_plan if kind == 'plan' else services.apply_course_draft)(store, key, value.version)


@router.get('/jobs')
def job_list(user=Depends(require_user)):
    return jobs.list_jobs(user['id'])


@router.post('/jobs', status_code=202)
def create_job(value: schemas.JobInput, user=Depends(require_user)):
    if value.kind == 'grade':
        raise ValueError('请从练习页面提交答案')
    payload = value.payload
    with records(user['id']) as store:
        if value.kind in ('week_plan', 'training_plan'):
            start = week_start(payload.get('week_start', today()))
            payload = {'week_start': start}
            profile = services.settings(store)
            if value.kind == 'training_plan' and not all(profile[k] for k in ('training_goal', 'recent_performance', 'weekly_mileage', 'training_days', 'injury_notes')):
                raise ValueError('请先在设置中填写训练目标、近期成绩、近四周跑量、可训练时间和身体状况（无不适可填“无”）')
            if value.kind == 'week_plan' and not profile['learning_goals']:
                raise ValueError('请先在设置中填写学习目标')
        if value.kind in ('quiz', 'word_enrich'):
            keys = payload.get('word_ids', [])
            if not keys or len(keys) > 20:
                raise ValueError('请选择 1–20 个单词')
            for key in keys:
                store.get('word', key)
            if value.kind == 'quiz' and payload.get('mode') not in ('dictation', 'translation', 'choice'):
                raise ValueError('请选择练习题型')
            if payload.get('direction', 'zh-en') not in ('zh-en', 'en-zh'):
                raise ValueError('翻译方向无效')
        if value.kind == 'news':
            payload = {'date': today()}
    return jobs.enqueue(user['id'], value.kind, payload)


@router.post('/jobs/{key}/{action}')
def update_job(key: str, action: Literal['retry', 'cancel'], user=Depends(require_user)):
    return jobs.change_job(user['id'], key, action)


@router.get('/questions')
def questions(job_id: str, user=Depends(require_user)):
    with records(user['id']) as store:
        return [{k: v for k, v in r.items() if k not in ('expected', 'explanation')} for r in store.list('question') if r.get('job_id') == job_id]


@router.post('/questions/{key}/answers')
def answer(key: str, value: schemas.Answer, user=Depends(require_user)):
    with records(user['id']) as store:
        result = services.submit_answer(store, key, value.answer)
    if result['status'] == 'pending':
        jobs.enqueue(user['id'], 'grade', {'attempt_id': result['id']}, dedup='grade-' + result['id'], priority=1)
    return result


@router.get('/attempts')
def attempts(user=Depends(require_user)):
    with records(user['id']) as store:
        return [{**r, 'expected': store.get('question', r['question_id'])['expected']} for r in store.list('attempt')[:100]]


@router.get('/word-suggestions')
def word_suggestions(user=Depends(require_user)):
    with records(user['id']) as store:
        return store.list('word_suggestions')[:10]


@router.post('/word-suggestions/{key}/adoption')
def adopt_words(key: str, value: schemas.Revision, user=Depends(require_user)):
    with records(user['id']) as store:
        draft = store.get('word_suggestions', key)
        if draft.get('applied'):
            return draft
        if draft['version'] != value.version:
            raise Conflict('词义草稿已更新，请刷新')
        for item in draft['words']:
            if item.get('word_id') not in draft['versions']:
                raise ValueError('AI 返回了无效词条')
            word = store.get('word', item['word_id'])
            if word['version'] != draft['versions'][word['id']]:
                raise Conflict('词条已修改，请重新生成补全建议')
            body = {k: word[k] for k in schemas.Word.model_fields}
            body.update({k: item[k] for k in ('meaning', 'part_of_speech', 'example')})
            services.save_resource(store, 'words', body, word['id'], word['version'])
        return store.save('word_suggestions', {**draft, 'applied': True}, key, value.version)


@router.post('/attempts/{key}/correction')
def correct_attempt(key: str, value: schemas.Review, user=Depends(require_user)):
    with records(user['id']) as store:
        old = store.get('attempt', key)
        if old['status'] != 'graded':
            raise Conflict('请等待批改完成')
        if old['correct'] != value.correct:
            word = store.get('word', old['word_id'])
            store.save('word', {**word, 'stage': 0, 'review_on': today(), 'wrong_count': max(0, word['wrong_count'] + (1 if not value.correct else -1))}, word['id'], word['version'])
        store.event('更正练习', {'title': old['word_id'], 'correct': value.correct})
        return store.save('attempt', {**old, 'correct': value.correct, 'feedback': '已由本人更正判分'}, key, old['version'])


@router.post('/course-imports', status_code=202)
async def course_import(file: UploadFile = File(), user=Depends(require_user)):
    from .uploads import save_upload
    with records(user['id']) as store:
        if not services.settings(store)['semester_start']:
            raise ValueError('请先在偏好与目标中填写学期开始日期及节次表，再导入课表')
    raw = await file.read(10 * 1024 * 1024 + 1)
    token = save_upload(raw, file.content_type)
    return jobs.enqueue(user['id'], 'course_import', {'upload': token})
