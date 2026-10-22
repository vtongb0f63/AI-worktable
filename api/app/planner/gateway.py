"""Private inference-only bridge to Codex app-server over stdio.

Run in a dedicated container without application data, SSH keys or Docker socket.
Only the app-server process sees its own subscription credentials.
"""
import json
import os
import queue
import secrets
import shutil
import subprocess
import threading
import time
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
lock = threading.Lock()


class Generate(BaseModel):
    prompt: str = Field(min_length=1, max_length=200000)
    images: list[str] = Field(default_factory=list, max_length=6)


def authorize(authorization: str = Header(default='')):
    token = os.environ.get('AI_GATEWAY_TOKEN', '')
    if not token or not secrets.compare_digest(authorization, 'Bearer ' + token):
        raise HTTPException(401, 'AI 通道身份验证失败')


def infer(prompt, images=None):
    binary = os.environ.get('CODEX_BINARY') or shutil.which('codex')
    if not binary:
        raise HTTPException(503, '服务器尚未安装 Codex')
    command = [binary, 'app-server', '--listen', 'stdio://']
    for feature in ('shell_tool', 'unified_exec', 'apps', 'plugins', 'multi_agent', 'multi_agent_v2', 'code_mode', 'code_mode_host'):
        command += ['--disable', feature]
    command += ['-c', 'web_search="disabled"', '-c', 'approval_policy="never"']
    # Dedicated CODEX_HOME has only auth, never user/project plugins or rules.
    cwd = Path(os.environ.get('AI_WORK_DIR', '/tmp/study-inference' if os.name != 'nt' else str(Path(os.environ['LOCALAPPDATA']) / 'StudyPlanner' / 'scratch')))
    cwd.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in ('AI_GATEWAY_TOKEN', 'OPENAI_API_KEY', 'ENCRYPTION_KEY', 'MAIL_PASSWORD')}
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', cwd=cwd, env=env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    lines = queue.Queue()

    def read():
        for line in proc.stdout:
            try:
                lines.put(json.loads(line))
            except ValueError:
                pass
        lines.put({'process_ended': True})

    threading.Thread(target=read, daemon=True).start()
    deadline = time.monotonic() + 420

    def send(method, params=None, id=None):
        value = {'method': method}
        if params is not None:
            value['params'] = params
        if id is not None:
            value['id'] = id
        proc.stdin.write(json.dumps(value, ensure_ascii=False) + '\n')
        proc.stdin.flush()

    def receive():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HTTPException(503, 'AI 响应超时，可稍后重试')
        try:
            message = lines.get(timeout=remaining)
        except queue.Empty:
            raise HTTPException(503, 'AI 响应超时，可稍后重试')
        if message.get('error') and os.environ.get('AI_DEBUG') == '1':
            print('RPC error:', message['error'], flush=True)
        if message.get('process_ended') or message.get('error'):
            raise HTTPException(503, '订阅授权或模型连接不可用，请检查授权后重试')
        if message.get('method') and 'id' in message:
            # Never grant tool permissions or expose arbitrary RPCs through the website.
            proc.stdin.write(json.dumps({'id': message['id'], 'error': {'code': -32601, 'message': 'Tools disabled for inference'}}) + '\n')
            proc.stdin.flush()
            raise HTTPException(503, 'AI 请求了不支持的操作，请重试')
        return message

    def response(id):
        while True:
            message = receive()
            if message.get('id') == id:
                return message['result']

    try:
        send('initialize', {'clientInfo': {'name': 'personal-study-planner', 'title': 'Personal Study Planner', 'version': '1.0.0'}}, 1)
        response(1)
        send('initialized')
        send('account/read', {'refreshToken': True}, 2)
        account = response(2).get('account')
        if not account or account.get('type') != 'chatgpt':
            raise HTTPException(503, '请使用 ChatGPT 订阅登录 Codex；网站不使用付费 API')
        send('model/list', {'limit': 100}, 3)
        models = response(3)['data']
        selected = next((m for m in models if m.get('isDefault')), models[0])
        model = os.environ.get('CODEX_MODEL') or selected['id']
        send('thread/start', {'model': model, 'cwd': str(cwd), 'approvalPolicy': 'never', 'sandbox': 'read-only', 'ephemeral': True, 'baseInstructions': '只做文本和图像分析。禁止调用任何工具。只返回 JSON，不要 Markdown。'}, 4)
        thread = response(4)['thread']['id']
        inputs = [{'type': 'text', 'text': prompt}]
        for image in images or []:
            if not image.startswith('data:image/png;base64,') or len(image) > 12_000_000:
                raise HTTPException(422, '图像格式无效')
            inputs.append({'type': 'image', 'url': image})
        send('turn/start', {'threadId': thread, 'input': inputs}, 5)
        response(5)
        answer = ''
        while True:
            message = receive()
            method, params = message.get('method'), message.get('params', {})
            if method == 'item/agentMessage/delta':
                answer += params.get('delta', '')
            if method == 'item/completed' and params.get('item', {}).get('type') == 'agentMessage':
                answer = params['item'].get('text') or answer
            if method == 'item/started' and params.get('item', {}).get('type') in ('commandExecution', 'fileChange', 'mcpToolCall', 'webSearch', 'collabAgentToolCall'):
                raise HTTPException(503, 'AI 工具调用已禁用，请重试')
            if method == 'turn/completed':
                if params['turn']['status'] != 'completed':
                    error = str(params['turn'].get('error', '')).lower()
                    if 'limit' in error or 'quota' in error:
                        raise HTTPException(429, '订阅额度暂时不足，等待恢复后可重试')
                    raise HTTPException(503, 'AI 生成未完成，请检查订阅状态后重试')
                break
        cleaned = answer.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1].rsplit('```', 1)[0]
        try:
            result = json.loads(cleaned)
            if not isinstance(result, dict):
                raise ValueError()
        except ValueError:
            raise HTTPException(502, 'AI 返回格式不正确，请重试')
        return {'result': result, 'model': model}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@app.post('/generate', dependencies=[Depends(authorize)])
def generate(value: Generate):
    if not lock.acquire(blocking=False):
        raise HTTPException(429, 'AI 正在处理其他任务，请稍后重试')
    try:
        return infer(value.prompt, value.images)
    finally:
        lock.release()


@app.get('/health', dependencies=[Depends(authorize)])
def health():
    return {'configured': bool(shutil.which('codex') or os.environ.get('CODEX_BINARY')), 'billing': 'subscription-only'}
