import io
import pytest
from PIL import Image
from test_app import client, make_user
from app import config
from app.db import connect
from app.planner import services, jobs, worker
from app.planner.domain import Conflict, course_occurrences, next_review, today
from app.planner.repository import records
from app.planner.schemas import Task, Course
from app.planner.ai_port import AIUnavailable


@pytest.fixture
def owner(client, monkeypatch):
    make_user(client, 'admin@example.com', 'admin', 'first-admin-code')
    monkeypatch.setattr(config, 'PRIVATE_MODE', True)
    monkeypatch.setattr(config, 'OWNER_EMAIL', 'admin@example.com')
    return client


def user_id():
    with connect() as db:
        return db.execute("SELECT id FROM users WHERE email='admin@example.com'").fetchone()[0]


def add(c, resource, data):
    response = c.post('/api/v1/records/' + resource, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def task(**kw):
    return Task(title='学习', date='2026-10-21', **kw).model_dump(mode='json')


def course(**kw):
    return Course(title='数学', weekday=2, semester_start='2026-10-19', start_time='08:00', end_time='09:00', **kw).model_dump(mode='json')


def test_private_surface(owner):
    assert owner.get('/api/public/admin').status_code == 404
    assert owner.post('/api/ai/test').status_code == 404
    assert owner.post('/api/nodes', json={}).status_code == 403
    assert owner.post('/api/auth/register', json={'email':'x@example.com','username':'test','password':'a-long-password-123','invite_code':'anything'}).status_code == 403
    assert owner.post('/api/v1/records/tasks', json=task(), headers={'Origin':'https://evil.example'}).status_code == 403
    owner.post('/api/auth/logout')
    assert owner.get('/api/v1/overview').status_code == 401


def test_non_owner_denied(client, monkeypatch):
    make_user(client, 'admin@example.com', 'admin', 'first-admin-code')
    code = client.post('/api/admin/invites', json={}).json()['code']
    client.post('/api/auth/logout')
    make_user(client, 'other@example.com', 'other', code)
    monkeypatch.setattr(config, 'PRIVATE_MODE', True)
    monkeypatch.setattr(config, 'OWNER_EMAIL', 'admin@example.com')
    assert client.get('/api/v1/overview').status_code == 403


def test_task_version_and_journal(owner):
    row = add(owner, 'tasks', task())
    response = owner.put('/api/v1/records/tasks/' + row['id'], json={'version':1,'data':task(status='done')})
    assert response.status_code == 200
    assert owner.put('/api/v1/records/tasks/' + row['id'], json={'version':1,'data':task()}).status_code == 409
    assert any(e['kind']=='完成' for e in owner.get('/api/v1/journal?day=2026-10-21').json()['items'])
    assert owner.put('/api/v1/records/tasks/' + row['id'], json={'version':2,'data':task()}).status_code == 200


def test_course_parity_exclusion():
    value = course(parity='odd', excluded_dates=['2026-11-04'])
    rows = course_occurrences([value], '2026-10-19', '2026-11-08')
    assert [r['date'] for r in rows] == ['2026-10-21']


def test_conflicts_both_directions(owner):
    add(owner, 'courses', course())
    assert owner.post('/api/v1/records/tasks', json=task(start_time='08:30',end_time='09:30')).status_code == 409
    add(owner, 'tasks', task(start_time='09:00',end_time='10:00'))
    assert owner.post('/api/v1/records/courses', json=course()).status_code == 409


def draft(store):
    return store.save('draft', {'week_start':'2026-10-19','snapshot':services.snapshot(store),'applied':False,'plan':{'summary':'周计划','tasks':[task(start_time='10:00',end_time='11:00')],'unscheduled':[]}})


def test_plan_adoption_idempotent(owner):
    with records(user_id()) as store:
        d = draft(store)
        services.apply_plan(store,d['id'],1)
        services.apply_plan(store,d['id'],1)
        assert len(store.list('task')) == 1


def test_stale_plan_keeps_user_data(owner):
    with records(user_id()) as store:
        d = draft(store)
        services.save_resource(store,'tasks',task())
        with pytest.raises(Conflict):
            services.apply_plan(store,d['id'],1)
        assert len(store.list('task')) == 1


def test_run_relink_and_delete(owner):
    a = add(owner,'tasks',task(category='training'))
    b = add(owner,'tasks',task(category='training'))
    data = {'date':'2026-10-21','distance_km':5,'duration_minutes':30,'effort':4,'task_id':a['id']}
    run = add(owner,'runs',data)
    assert owner.delete('/api/v1/records/tasks/'+a['id']+'?version=2').status_code == 409
    assert owner.put('/api/v1/records/runs/'+run['id'],json={'version':1,'data':{**data,'task_id':b['id']}}).status_code == 200
    rows = {t['id']:t for t in owner.get('/api/v1/records/tasks').json()['items']}
    assert rows[a['id']]['status']=='pending' and rows[b['id']]['status']=='done'
    assert owner.delete('/api/v1/records/runs/'+run['id']+'?version=2').status_code == 204
    rows = {t['id']:t for t in owner.get('/api/v1/records/tasks').json()['items']}
    assert rows[b['id']]['status']=='pending'


class NoAI:
    def generate(self,*args):
        raise AIUnavailable('订阅暂时不可用')


def test_dictation_works_without_ai_and_no_double_grading(owner):
    word = add(owner,'words',{'term':'Resilience','meaning':'韧性'})
    j = owner.post('/api/v1/jobs',json={'kind':'quiz','payload':{'word_ids':[word['id']],'mode':'dictation'}}).json()
    assert worker.tick(NoAI())
    q = owner.get('/api/v1/questions?job_id='+j['id']).json()[0]
    assert 'expected' not in q
    path = '/api/v1/questions/'+q['id']+'/answers'
    result = owner.post(path,json={'answer':' resilience '})
    assert result.json()['correct'] is True
    assert owner.post(path,json={'answer':'wrong'}).status_code == 409
    assert owner.get('/api/v1/records/words').json()['items'][0]['stage'] == 1


def test_translation_quota_does_not_mark_wrong(owner):
    w = add(owner,'words',{'term':'run','meaning':'跑步'})
    with records(user_id()) as store:
        q=store.save('question',{'word_id':w['id'],'mode':'translation','prompt':'我跑步。','expected':'I run.','options':[],'explanation':''})
    attempt=owner.post('/api/v1/questions/'+q['id']+'/answers',json={'answer':'I run.'}).json()
    worker.tick(NoAI())
    assert owner.get('/api/v1/jobs').json()[0]['status']=='blocked'
    assert owner.get('/api/v1/records/words').json()['items'][0]['wrong_count']==0
    assert attempt['status']=='pending'


def test_cancel_during_inference_cannot_write(owner):
    j=jobs.enqueue(user_id(),'week_plan',{})
    claimed=jobs.claim()
    jobs.change_job(user_id(),j['id'],'cancel')
    worker.finish(claimed,{'type':'draft','data':{'plan':{}}})
    with records(user_id()) as store:
        assert store.list('draft')==[]


def test_review_intervals_and_csv(owner):
    assert next_review(0,True,'2026-10-21')==(1,'2026-10-22')
    assert next_review(2,True,'2026-10-21')==(3,'2026-10-28')
    assert next_review(6,False,'2026-10-21')==(0,'2026-10-22')
    result=owner.post('/api/v1/words/import',files={'file':('words.csv',b'term,meaning\nrun,running\nRUN,duplicate\n','text/csv')})
    assert result.json()=={'imported':1,'skipped':1}


def test_word_filter_before_pagination(owner):
    with records(user_id()) as store:
        for i in range(55):
            store.save('word',{'term':str(i),'review_on':today(),'wrong_count':int(i==0),'stage':0})
    result=owner.get('/api/v1/records/words?filter=wrong&limit=10').json()
    assert result['total']==1 and result['items'][0]['term']=='0'


def test_upload_validation(owner,monkeypatch,tmp_path):
    from app.planner.uploads import save_upload, load_upload
    monkeypatch.setattr(config,'UPLOAD_DIR',tmp_path/'uploads')
    with pytest.raises(ValueError):
        save_upload(b'not an image','image/png')
    raw=io.BytesIO();Image.new('RGB',(20,20)).save(raw,format='PNG')
    key=save_upload(raw.getvalue(),'image/png')
    assert load_upload(key)[1][0].startswith('data:image/png;base64,')
    with pytest.raises(ValueError):
        load_upload('../bad')
