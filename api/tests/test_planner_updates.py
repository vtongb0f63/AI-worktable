"""Regression coverage for compatibility, scoped AI edits and training date windows."""
import json
from datetime import date, timedelta
import pytest
from test_app import client
from test_planner import owner, user_id, add, draft
from app.planner.schemas import Task
from app.planner import services, jobs, worker
from app.planner.repository import records
from app.planner.domain import Conflict


def task(**values):
    return Task.model_validate({'title': '学习', 'date': '2026-10-21', **values}).model_dump(mode='json')


class Reply:
    def __init__(self, value):
        self.value, self.request = value, ''

    def generate(self, request):
        self.request = request
        return self.value


def make_plan():
    with records(user_id()) as store:
        d = draft(store)
        plan = {**d['plan'], 'tasks': [task(title='保留原样', start_time='08:00', end_time='09:00'),
                                     task(title='需要调整', start_time='10:00', end_time='11:00')]}
        return store.save('draft', {**d, 'kind': 'week_plan', 'plan': plan}, d['id'], d['version'])


def revision(owner, d, **extra):
    response = owner.post(f"/api/v1/drafts/plan/{d['id']}/revisions", json={
        'version': d['version'], 'selected_indices': [1], 'feedback': '把第二项移到下午', **extra})
    assert response.status_code == 202, response.text
    return jobs.claim()


def test_phonetics_old_words_and_suggestions(owner):
    w = add(owner, 'words', {'term': 'run', 'phonetic_uk': '/rʌn/'})
    assert w['phonetic_uk'] == '/rʌn/'
    # An older client omitting the new field must not clear the saved pronunciation.
    response = owner.put('/api/v1/records/words/' + w['id'], json={'version': w['version'], 'data': {'term': 'run', 'meaning': '跑'}})
    assert response.json()['phonetic_uk'] == '/rʌn/'
    with records(user_id()) as store:
        w = store.get('word', w['id'])
        suggestion = store.save('word_suggestions', {'words': [{'word_id': w['id'], 'meaning': '跑步', 'part_of_speech': 'v.', 'example': 'I run.'}], 'versions': {w['id']: w['version']}})
        legacy = store.save('word', {'term': 'legacy', 'meaning': '', 'part_of_speech': '', 'example': '', 'source': '', 'tags': '', 'stage': 0, 'review_on': '2026-10-21', 'wrong_count': 0})
        assert legacy['phonetic_uk'] == ''
    assert owner.post(f"/api/v1/word-suggestions/{suggestion['id']}/adoption", json={'version': 1, 'data': {}}).status_code == 200
    words = owner.get('/api/v1/records/words').json()['items']
    assert next(r for r in words if r['id'] == w['id'])['phonetic_uk'] == '/rʌn/'
    model = Reply({'words': [{'word_id': legacy['id'], 'meaning': '遗产', 'part_of_speech': 'n.', 'example': '', 'phonetic_uk': '/ˈleɡəsi/'}]})
    prepared = worker.prepare({'user_id': user_id(), 'kind': 'word_enrich', 'payload': {'word_ids': [legacy['id']]}}, model)
    assert '英式国际音标' in model.request
    with records(user_id()) as store:
        s = store.save('word_suggestions', prepared['data'])
    assert owner.post(f"/api/v1/word-suggestions/{s['id']}/adoption", json={'version': 1, 'data': {}}).status_code == 200
    assert next(r for r in owner.get('/api/v1/records/words').json()['items'] if r['id'] == legacy['id'])['phonetic_uk'] == '/ˈleɡəsi/'
    with records(user_id()) as store:
        assert store.list('journal_event') == []


def test_journal_filters_before_pagination_and_keeps_practice(owner):
    with records(user_id()) as store:
        for _ in range(60):
            store.event('添加', {'resource': '词汇', 'title': 'hidden'}, '2026-10-21')
            store.event('修改', {'resource': '词汇', 'title': 'hidden'}, '2026-10-21')
        store.event('词汇练习', {'title': 'visible'}, '2026-10-21')
        store.event('添加', {'resource': '训练', 'title': 'run'}, '2026-10-21')
    data = owner.get('/api/v1/journal?day=2026-10-21&limit=1').json()
    assert data['total'] == 2 and len(data['items']) == 1
    assert data['items'][0]['detail']['title'] != 'hidden'
    with records(user_id()) as store:
        assert len(store.list('journal_event')) == 122


def test_run_type_edit_preserves_hidden_fields_and_task_status(owner):
    t = add(owner, 'tasks', task(category='training'))
    data = {'date': t['date'], 'distance_km': 3, 'duration_minutes': 20, 'effort': 4, 'status': 'partial', 'discomfort': '历史身体反馈', 'task_id': t['id']}
    r = add(owner, 'runs', data)
    assert r['training_type'] == ''
    visible = {k: v for k, v in data.items() if k not in ('status', 'discomfort')}
    edited = owner.put('/api/v1/records/runs/' + r['id'], json={'version': 1, 'data': {**visible, 'training_type': 'easy'}}).json()
    assert (edited['training_type'], edited['status'], edited['discomfort']) == ('easy', 'partial', '历史身体反馈')
    assert owner.get('/api/v1/records/tasks').json()['items'][0]['status'] == 'partial'
    assert add(owner, 'runs', {**visible, 'task_id': None, 'training_type': 'tempo'})['status'] == 'done'
    assert owner.post('/api/v1/records/runs', json={**visible, 'training_type': 'invented'}).status_code == 422


@pytest.mark.parametrize('start', ['2026-11-02', '2027-01-04'])
def test_three_full_weeks_all_records_by_run_date(owner, start):
    target = date.fromisoformat(start)
    with records(user_id()) as store:
        for offset in range(-22, 2):
            for _ in range(2):
                store.save('run', {'date': (target + timedelta(days=offset)).isoformat(), 'distance_km': 2,
                    'duration_minutes': 12, 'effort': 4, 'status': 'done', 'training_type': 'easy'})
        # A late-created historical record must be included by date, not insertion order.
        store.save('run', {'date': (target - timedelta(days=20)).isoformat(), 'distance_km': 1,
            'duration_minutes': 6, 'effort': 7, 'status': 'partial'})
        history = services.training_history(store, start)
    assert len(history['runs']) == 43
    assert history['start'] == (target - timedelta(days=21)).isoformat()
    assert history['end'] == (target - timedelta(days=1)).isoformat()
    assert [w['count'] for w in history['weeks']] == [15, 14, 14]
    assert sum(w['distance_km'] for w in history['weeks']) == 85
    assert history['weeks'][0]['training_types'] == {'easy': 14, 'unclassified': 1}
    assert history['weeks'][0]['average_effort'] == 4.2


def test_training_prompt_explicit_missing_weeks(owner):
    model = Reply({'summary': '缺少历史记录', 'tasks': [], 'unscheduled': []})
    worker.prepare({'user_id': user_id(), 'kind': 'training_plan', 'payload': {'week_start': '2027-01-04'}}, model)
    context = json.loads(model.request.split('\n输入数据：')[1])
    assert len(context['training_history']['weeks']) == 3
    assert all(w['data_missing'] and w['average_effort'] is None for w in context['training_history']['weeks'])
    assert '近四周' not in model.request


def test_rejection_persists_and_cannot_adopt_or_edit(owner):
    d = make_plan()
    assert owner.post(f"/api/v1/drafts/plan/{d['id']}/rejection", json={'version': d['version'] - 1, 'data': {}}).status_code == 409
    response = owner.post(f"/api/v1/drafts/plan/{d['id']}/rejection", json={'version': d['version'], 'data': {}})
    assert response.json()['rejected'] is True
    v = response.json()['version']
    assert owner.put(f"/api/v1/drafts/plan/{d['id']}", json={'version': v, 'data': d['plan']}).status_code == 409
    assert owner.post(f"/api/v1/drafts/plan/{d['id']}/adoption", json={'version': v, 'data': {}}).status_code == 409
    assert owner.get('/api/v1/records/tasks').json()['total'] == 0
    assert owner.get('/api/v1/drafts').json()['plans'][0]['rejected'] is True


def test_scoped_revision_same_draft_untouched_items_and_adoption(owner):
    d = make_plan()
    j = revision(owner, d)
    model = Reply({'replacements': [{'index': 1, 'tasks': [task(title='下午安排一', start_time='14:00', end_time='14:30'), task(title='下午安排二', start_time='14:30', end_time='15:00')]}]})
    worker.finish(j, worker.prepare(j, model))
    with records(user_id()) as store:
        result = store.get('draft', d['id'])
        assert len(store.list('draft')) == 1 and not result['applied']
        assert result['plan']['tasks'][0] == d['plan']['tasks'][0]
        assert result['plan']['summary'] == d['plan']['summary']
        assert result['last_revision']['changed_indices'] == [1, 2]
        assert store.list('task') == []
    assert owner.post(f"/api/v1/drafts/plan/{d['id']}/adoption", json={'version': result['version'], 'data': {}}).status_code == 200
    assert owner.get('/api/v1/records/tasks').json()['total'] == 3


@pytest.mark.parametrize('change', ['edit', 'adopt', 'reject', 'cancel', 'records'])
def test_revision_cannot_overwrite_changed_or_cancelled_state(owner, change):
    d = make_plan()
    j = revision(owner, d)
    result = worker.prepare(j, Reply({'replacements': [{'index': 1, 'tasks': [task(title='不应写入', start_time='14:00', end_time='15:00')]}]}))
    if change == 'edit':
        assert owner.put(f"/api/v1/drafts/plan/{d['id']}", json={'version': d['version'], 'data': {**d['plan'], 'summary': '用户修改'}}).status_code == 200
    elif change == 'adopt':
        assert owner.post(f"/api/v1/drafts/plan/{d['id']}/adoption", json={'version': d['version'], 'data': {}}).status_code == 200
    elif change == 'reject':
        assert owner.post(f"/api/v1/drafts/plan/{d['id']}/rejection", json={'version': d['version'], 'data': {}}).status_code == 200
    elif change == 'records':
        add(owner, 'tasks', task(title='另一个任务'))
    else:
        jobs.change_job(user_id(), j['id'], 'cancel')
    if change == 'cancel':
        worker.finish(j, result)
    else:
        with pytest.raises(Conflict):
            worker.finish(j, result)
    with records(user_id()) as store:
        assert store.get('draft', d['id'])['plan']['tasks'] == d['plan']['tasks']


@pytest.mark.parametrize('case', ['unselected', 'missing', 'duplicate', 'delete', 'outside', 'overlap'])
def test_invalid_ai_revisions_leave_original(owner, case):
    d = make_plan()
    j = revision(owner, d)
    replacement = {'index': 1, 'tasks': [task(title='变化', start_time='14:00', end_time='15:00')]}
    items = [replacement]
    if case == 'unselected':
        replacement['index'] = 0
    elif case == 'missing':
        items = []
    elif case == 'duplicate':
        items = [replacement, replacement]
    elif case == 'delete':
        replacement['tasks'] = []
    elif case == 'outside':
        replacement['tasks'][0]['date'] = '2026-10-26'
    else:
        replacement['tasks'][0].update(start_time='08:30', end_time='09:30')
    with pytest.raises((ValueError, Conflict)):
        worker.finish(j, worker.prepare(j, Reply({'replacements': items})))
    with records(user_id()) as store:
        assert store.get('draft', d['id'])['plan'] == d['plan']


def test_explicit_removal_and_input_validation(owner):
    d = make_plan()
    for indices in ([], [0, 0], [-1], [2]):
        assert owner.post(f"/api/v1/drafts/plan/{d['id']}/revisions", json={'version': d['version'], 'selected_indices': indices, 'feedback': '修改'}).status_code in (400, 422)
    j = revision(owner, d, allow_removal=True, feedback='删除选中的安排')
    worker.finish(j, worker.prepare(j, Reply({'replacements': [{'index': 1, 'tasks': []}]})))
    with records(user_id()) as store:
        result = store.get('draft', d['id'])
        assert result['plan']['tasks'] == [d['plan']['tasks'][0]]
        assert result['last_revision']['changes'][0]['after'] == []
