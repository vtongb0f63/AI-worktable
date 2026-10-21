"""Local-only browser checks. Start the isolated API and web server first.

PYTHONPATH=api DATABASE_PATH=.local/e2e.db python scripts/e2e.py
The owner@example.com fixture belongs only in that disposable database.
"""
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'
os.environ.setdefault('DATABASE_PATH', str(Path('.local/e2e.db').resolve()))
from app.planner import worker, services
from app.planner.repository import records
from app.planner.domain import today, week_start


def main():
    if Path(os.environ['DATABASE_PATH']).resolve() != Path('.local/e2e.db').resolve():
        raise RuntimeError('E2E requires the isolated .local/e2e.db database')
    output = Path('.local/screenshots'); output.mkdir(parents=True, exist_ok=True)
    suffix = str(int(time.time()))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1440,'height':1000})
        errors=[]
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE+'/login');page.wait_for_load_state('networkidle')
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'), 'mobile login overflows'
        page.set_viewport_size({'width':1440,'height':1000})
        page.get_by_label('邮箱',exact=True).fill('owner@example.com')
        page.get_by_label('密码',exact=True).fill('local-e2e-password')
        page.get_by_role('button',name='进入我的工作台').click()
        page.wait_for_url('**/today')
        page.get_by_role('button',name='＋ 添加待办').click()
        dialog=page.get_by_role('dialog')
        title='浏览器测试 '+suffix
        dialog.get_by_label('要做什么').fill(title)
        dialog.get_by_role('button',name='保存',exact=True).click()
        expect(dialog).not_to_be_visible()
        page.get_by_label('完成：'+title,exact=True).click()
        expect(page.get_by_label('撤销完成：'+title,exact=True)).to_be_checked()
        page.reload()
        page.get_by_text('已完成',exact=False).first.wait_for()
        checkbox=page.get_by_label('撤销完成：'+title,exact=True)
        if not checkbox.is_visible():
            page.locator('summary').filter(has_text='已完成').click()
        checkbox.click()
        expect(page.get_by_label('完成：'+title,exact=True)).not_to_be_checked()
        page.screenshot(path=str(output/'today-desktop.png'),full_page=True)

        page.goto(BASE+'/words');page.wait_for_load_state('networkidle')
        page.get_by_role('button',name='＋ 添加生词').click()
        dialog.get_by_label('单词或短语').fill('resilience'+suffix)
        dialog.get_by_label('中文释义').fill('韧性；恢复能力')
        dialog.get_by_role('button',name='保存',exact=True).click()
        page.get_by_label('选择 resilience'+suffix,exact=True).check()
        page.get_by_role('button',name='开始练习').click()
        page.wait_for_url('**/words?quiz=*')
        worker.tick()
        page.get_by_role('button',name='刷新题目').click()
        page.get_by_label('填写单词').fill('resilience'+suffix)
        page.get_by_role('button',name='提交答案').click()
        expect(page.get_by_text('回答正确',exact=True).first).to_be_visible()

        # A deterministic draft verifies adoption UI without consuming subscription quota.
        with records('e2e-owner') as store:
            store.save('draft',{'kind':'week_plan','week_start':week_start(today()),'snapshot':services.snapshot(store),'applied':False,'plan':{'summary':'浏览器验收草稿 '+suffix,'tasks':[{'title':'计划任务 '+suffix,'date':today(),'category':'study'}],'unscheduled':[]}})
        page.goto(BASE+'/schedule');page.wait_for_load_state('networkidle')
        print('SCHEDULE BUTTONS', page.get_by_role('button').all_text_contents())
        page.screenshot(path=str(output/'schedule-desktop.png'),full_page=True)
        page.get_by_role('button',name='采用',exact=False).first.click()
        expect(page.get_by_text('计划任务 '+suffix,exact=True).first).to_be_visible()

        page.goto(BASE+'/running');page.wait_for_load_state('networkidle')
        page.get_by_role('button',name='＋ 记录一次训练').click()
        dialog.get_by_label('距离（公里）').fill('5')
        dialog.get_by_label('用时（分钟）').fill('30')
        dialog.get_by_role('button',name='保存',exact=True).click()
        expect(dialog).not_to_be_visible()
        expect(page.locator('.run-row').first).to_be_visible()

        page.goto(BASE+'/journal');page.wait_for_load_state('networkidle')
        page.get_by_label('今日复盘').fill('今天完成了浏览器联调 '+suffix)
        page.get_by_role('button',name='留在这一页').click()
        expect(page.get_by_text('今天完成了浏览器联调 '+suffix,exact=True)).to_be_visible()
        for section in ['today','schedule','news','words','running','journal','settings','history']:
            page.set_viewport_size({'width':390,'height':844})
            page.goto(BASE+'/'+section);page.wait_for_load_state('networkidle')
            expect(page.locator('h1')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'), section+' overflows'
            page.screenshot(path=str(output/(section+'-mobile.png')),full_page=True)
        page.goto(BASE+'/schedule');page.wait_for_load_state('networkidle')
        page.get_by_label('下一周').click()
        expect(page.locator('.week-day.selected-day')).to_be_visible()
        page.get_by_label('退出登录').click()
        page.wait_for_url('**/login')
        assert not errors, errors
        browser.close()
        print('PASS: login, task persistence/undo, vocabulary dictation, plan adoption, running, journal, 8 mobile pages, next week, logout; no page errors')


if __name__=='__main__':
    main()
