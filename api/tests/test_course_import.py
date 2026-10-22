import pytest
from app.planner.course_import import normalize, settings_periods
from app.planner.schemas import Course
from test_app import client
from test_planner import owner, user_id

PROFILE={'semester_start':'2026-09-14','periods':'第1大节 08:15-09:55\n第5大节 19:20-21:55'}


def row(**kw):
    return {'title':'AI编程基础','weekday':3,'start_week':1,'end_week':16,**kw}


def test_small_periods_override_partial_or_whole_block_guess():
    result=normalize({'period_times':[{'number':10,'start_time':'19:20','end_time':'20:05'},{'number':11,'start_time':'20:15','end_time':'21:00'},{'number':12,'start_time':'21:10','end_time':'21:55'}], 'courses':[row(period_numbers=[10,11],start_time='19:20',end_time=None),row(title='AI编程实训',period_numbers=[12],start_time=None,end_time=None)]},PROFILE)
    assert [(x['start_time'],x['end_time']) for x in result['courses']]==[('19:20','21:00'),('21:10','21:55')]
    for x in result['courses']:Course.model_validate(x)


def test_incomplete_course_kept_without_losing_valid_rows():
    result=normalize({'courses':[row(start_time='8:15',end_time='09:55'),row(title='截图底部课程',start_time='21:10',end_time=None)]},PROFILE)
    assert len(result['courses'])==2
    assert result['courses'][0]['start_time']=='08:15'
    assert result['courses'][1]['end_time'] is None
    assert any('截图底部课程' in warning for warning in result['warnings'])
    with pytest.raises(ValueError):Course.model_validate(result['courses'][1])


def test_partial_block_never_fills_entire_evening():
    result=normalize({'courses':[row(period_numbers=[12],block_number=5,covers_full_block=False)]},PROFILE)
    assert result['courses'][0]['start_time'] is None
    result=normalize({'courses':[row(block_number=5,covers_full_block=True)]},PROFILE)
    assert result['courses'][0]['start_time']=='19:20'
    assert result['courses'][0]['end_time']=='21:55'


def test_configured_small_periods_and_semester_are_authoritative():
    profile={**PROFILE,'periods':'第1节 08:00-08:45\n第2节 08:55-09:40'}
    result=normalize({'period_times':[{'number':1,'start_time':'08:15','end_time':'09:00'}],'courses':[row(period_numbers=[1,2],semester_start='2026-10-19')]},profile)
    assert result['courses'][0]['start_time']=='08:00'
    assert result['courses'][0]['end_time']=='09:40'
    assert result['courses'][0]['semester_start']=='2026-09-14'


def test_unknown_weeks_and_weekday_are_explicitly_flagged():
    result=normalize({'courses':[row(weekday=None,start_week=None,end_week=None)]},PROFILE)
    assert result['courses'][0]['weekday'] is None
    assert len(result['warnings'])==3


def test_empty_or_malformed_extraction_is_readable():
    for value in ({'courses':[]},{},[]):
        with pytest.raises(ValueError, match='课'):
            normalize(value,PROFILE)


def test_block_parser_does_not_confuse_small_period_numbers():
    small,blocks=settings_periods('第1大节 8:15—09:55\n第1节 08:15-09:00')
    assert small[1]==('08:15','09:00')
    assert blocks[1]==('08:15','09:55')


def test_worker_saves_partial_draft_then_requires_correction(owner,monkeypatch):
    from app.planner import jobs, worker, uploads
    from app.planner.schemas import Settings
    from app.planner.repository import records
    with records(user_id()) as store:
        store.save('settings',Settings(**PROFILE).model_dump(mode='json'))
    monkeypatch.setattr(uploads,'load_upload',lambda key: ('',[]))
    class FakeVision:
        def generate(self,*args):
            return {'courses':[row(start_time='19:20',end_time='21:00'),row(title='实训',start_time='21:10',end_time=None)]}
    job=jobs.enqueue(user_id(),'course_import',{'upload':'test'})
    assert worker.tick(FakeVision())
    assert jobs.list_jobs(user_id())[0]['status']=='done'
    draft=owner.get('/api/v1/drafts').json()['courses'][0]
    path='/api/v1/drafts/course/'+draft['id']
    assert len(draft['courses'])==2
    assert owner.post(path+'/adoption',json={'version':1,'data':{}}).status_code==422
    assert owner.get('/api/v1/records/courses').json()['total']==0
    draft['courses'][1]['end_time']='21:55'
    assert owner.put(path,json={'version':1,'data':{'courses':draft['courses']}}).status_code==200
    assert owner.post(path+'/adoption',json={'version':2,'data':{}}).status_code==200
    assert owner.post(path+'/adoption',json={'version':2,'data':{}}).status_code==200
    assert owner.get('/api/v1/records/courses').json()['total']==2
