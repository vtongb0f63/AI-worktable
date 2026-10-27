"""Browser regression checks with a disposable local DB and deterministic AI replies.

Start API with --serve-api and the web server on port 3000, then run this script.
Never uses the live site, subscription quota or production data.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / '.local' / 'planner-updates-e2e.db'
os.environ['DATABASE_PATH'] = str(DATABASE)
os.environ['OWNER_EMAIL'] = 'owner@example.com'
os.environ['PRIVATE_MODE'] = 'true'
os.environ['APP_ORIGIN'] = 'http://localhost:3000'
from app.db import init_db, transaction
from app.security import ph, iso
from app.planner import services, worker
from app.planner.repository import records
from app.planner.domain import today, week_start
from app.planner.schemas import Task


class RevisionAI:
    def generate(self, request):
        return {'replacements': [{'index': 1, 'tasks': [Task(title='调整后的安排', date=today(), start_time='15:00', end_time='15:30').model_dump(mode='json')]}]}


def seed():
    init_db()
    with transaction() as db:
        db.execute('INSERT OR IGNORE INTO users(id,email,username,password_hash,verified_at,created_at,is_admin) VALUES(?,?,?,?,?,?,1)',
                   ('e2e-owner', 'owner@example.com', 'learner', ph.hash('local-e2e-password'), iso(), iso()))


def main():
    from playwright.sync_api import sync_playwright, expect
    output = ROOT / '.local' / 'screenshots' / 'planner-updates'
    output.mkdir(parents=True, exist_ok=True)
    suffix = str(time.time_ns())
    term = 'resilience' + suffix
    base = 'http://localhost:3000'
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base + '/login')
        page.wait_for_load_state('networkidle')
        page.get_by_label('邮箱', exact=True).fill('owner@example.com')
        page.get_by_label('密码', exact=True).fill('local-e2e-password')
        page.get_by_role('button', name='进入我的工作台').click()
        page.wait_for_url('**/today')
        # Every sidebar destination, including brand/settings/history, replaces history.
        page.wait_for_load_state('networkidle')
        initial_history = page.evaluate('history.length')
        for label, path in [('周日程', 'schedule'), ('每日新闻', 'news'), ('词汇学习', 'words'), ('跑步', 'running'), ('日志', 'journal'), ('偏好与目标', 'settings'), ('历史目标', 'history')]:
            page.locator(f'.sidebar a[href="/{path}"]').click()
            page.wait_for_url('**/' + path)
            page.wait_for_load_state('networkidle')
            assert page.evaluate('history.length') == initial_history, label
        page.locator('a.brand').click()
        page.wait_for_url('**/today')
        assert page.evaluate('history.length') == initial_history

        page.get_by_role('link', name='词汇学习').click()
        page.wait_for_url('**/words')
        page.get_by_role('button', name='＋ 添加生词').click()
        dialog = page.get_by_role('dialog')
        dialog.get_by_label('单词或短语').fill(term)
        dialog.get_by_label('英式音标').fill('/rɪˈzɪliəns/')
        dialog.get_by_label('中文释义').fill('韧性')
        dialog.get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible()
        row = page.locator('.word-row').filter(has_text=term)
        expect(row.get_by_text('英 /rɪˈzɪliəns/', exact=True)).to_be_visible()
        row.get_by_role('button', name='编辑词条').click()
        expect(dialog.get_by_label('英式音标')).to_have_value('/rɪˈzɪliəns/')
        dialog.get_by_label('中文释义').fill('韧性；恢复能力')
        dialog.get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible()
        with records('e2e-owner') as store:
            word = next(w for w in store.list('word') if w['term'] == term)
            suggestion = store.save('word_suggestions', {'words': [{'word_id': word['id'], 'phonetic_uk': '/rɪˈzɪliəns/', 'meaning': '恢复力', 'part_of_speech': 'n.', 'example': 'Resilience matters.'}], 'versions': {word['id']: word['version']}})
        page.reload()
        page.wait_for_load_state('networkidle')
        preview = page.locator('.draft-panel').filter(has_text='AI 词义补全').filter(has_text=term)
        expect(preview.get_by_text('英 /rɪˈzɪliəns/', exact=True)).to_be_visible()
        preview.get_by_role('button', name='采用词义补全').click()
        expect(preview).not_to_be_visible()
        expect(row.get_by_text('恢复力', exact=True)).to_be_visible()
        page.screenshot(path=str(output / 'words-desktop.png'), full_page=True)
        with records('e2e-owner') as store:
            assert not [e for e in store.list('journal_event') if e.get('detail', {}).get('record_id') == word['id']]
            draft = store.save('draft', {'kind': 'week_plan', 'week_start': week_start(today()), 'snapshot': services.snapshot(store), 'applied': False,
                'plan': {'summary': '局部修改浏览器验收 ' + suffix, 'tasks': [Task(title='必须保持原样', date=today(), start_time='08:00', end_time='09:00').model_dump(mode='json'), Task(title='选中修改的安排', date=today(), start_time='10:00', end_time='11:00').model_dump(mode='json')], 'unscheduled': []}})
        page.get_by_role('link', name='周日程').click()
        page.wait_for_url('**/schedule')
        panel = page.locator('.draft-panel').filter(has_text=suffix)
        panel.get_by_role('button', name='否决这个计划', exact=True).click()
        expect(dialog.get_by_role('button', name='直接否决', exact=True)).to_be_visible()
        expect(dialog.get_by_role('button', name='告诉AI如何做得不同')).to_be_visible()
        dialog.get_by_role('button', name='取消', exact=True).click()
        expect(dialog).not_to_be_visible()
        with records('e2e-owner') as store:
            assert store.get('draft', draft['id'])['version'] == draft['version']
        panel.get_by_role('button', name='否决这个计划', exact=True).click()
        dialog.get_by_role('button', name='告诉AI如何做得不同').click()
        expect(dialog.get_by_role('button', name='提交局部修改')).to_be_disabled()
        dialog.get_by_label('选中修改的安排', exact=False).check()
        dialog.get_by_label('希望如何调整').fill('只把选中安排挪到下午三点')
        page.screenshot(path=str(output / 'feedback-desktop.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert dialog.evaluate('(element) => element.scrollWidth <= element.clientWidth + 1')
        page.screenshot(path=str(output / 'feedback-mobile.png'), full_page=True)
        dialog.get_by_role('button', name='提交局部修改').click()
        expect(dialog).not_to_be_visible()
        worker.tick(RevisionAI())
        expect(page.get_by_text('调整后的安排', exact=True).first).to_be_visible(timeout=15000)
        panel = page.locator('.draft-panel').filter(has_text=suffix)
        expect(panel.get_by_text('必须保持原样', exact=True)).to_be_visible()
        expect(panel.get_by_text('已按反馈调整', exact=True)).to_be_visible()
        panel.locator('summary').filter(has_text='查看本次修改').click()
        expect(panel.get_by_text('你的说明：只把选中安排挪到下午三点')).to_be_visible()
        with records('e2e-owner') as store:
            result = store.get('draft', draft['id'])
            assert result['plan']['tasks'][0] == draft['plan']['tasks'][0]
            assert not result['applied'] and not store.list('task')
        page.screenshot(path=str(output / 'revision-mobile.png'), full_page=True)
        panel.get_by_role('button', name='否决这个计划', exact=True).click()
        dialog.get_by_role('button', name='直接否决', exact=True).click()
        expect(panel).not_to_be_visible()
        page.reload()
        expect(page.locator('.draft-panel').filter(has_text=suffix)).not_to_be_visible()

        page.get_by_role('navigation', name='主导航').get_by_role('link', name='跑步', exact=False).click()
        page.wait_for_url('**/running')
        page.get_by_role('button', name='＋ 记录一次训练').click()
        expect(dialog.get_by_label('完成情况', exact=True)).to_have_count(0)
        expect(dialog.get_by_label('身体不适（可选）', exact=True)).to_have_count(0)
        dialog.get_by_label('训练项目', exact=True).select_option('easy')
        assert dialog.get_by_label('训练项目', exact=True).locator('option').count() == 10
        dialog.get_by_label('距离（公里）').fill('5')
        dialog.get_by_label('用时（分钟）').fill('30')
        assert dialog.evaluate('(element) => element.scrollWidth <= element.clientWidth + 1')
        page.screenshot(path=str(output / 'run-form-mobile.png'), full_page=True)
        dialog.get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible()
        expect(page.locator('.run-row').first.get_by_text('轻松跑', exact=True)).to_be_visible()
        page.locator('.run-row').first.get_by_role('button', name='编辑', exact=True).click()
        expect(dialog.get_by_label('训练项目', exact=True)).to_have_value('easy')
        dialog.get_by_label('训练项目', exact=True).select_option('recovery')
        dialog.get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible()
        expect(page.locator('.run-row').first.get_by_text('恢复跑', exact=True)).to_be_visible()
        page.set_viewport_size({'width': 1440, 'height': 1000})
        page.screenshot(path=str(output / 'running-desktop.png'), full_page=True)
        for section in ['today', 'schedule', 'news', 'words', 'running', 'journal', 'settings', 'history']:
            page.set_viewport_size({'width': 390, 'height': 844})
            page.goto(base + '/' + section)
            page.wait_for_load_state('networkidle')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), section
        page.get_by_label('退出登录', exact=True).click()
        page.wait_for_url('**/login')
        assert not errors, errors
        browser.close()
    print('PASS: navigation history, UK phonetics/edit/adoption, journal suppression, cancel/reject/scoped revision, training type, 8 mobile pages and logout; no page errors')


if __name__ == '__main__':
    seed()
    if '--serve-api' in sys.argv:
        import uvicorn
        uvicorn.run('app.main:app', host='127.0.0.1', port=8000)
    else:
        main()
