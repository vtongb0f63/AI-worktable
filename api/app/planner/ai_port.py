"""Inference port and authenticated HTTP adapter; no persistence or tools."""
from typing import Protocol
import httpx
from .. import config


class AIUnavailable(RuntimeError):
    pass


class AIProvider(Protocol):
    def generate(self, prompt: str, images: list[str] | None = None) -> dict: ...


class GatewayProvider:
    def generate(self, prompt, images=None):
        if not config.AI_GATEWAY_TOKEN:
            raise AIUnavailable('AI 尚未连接订阅，请完成服务器授权后重试')
        try:
            response = httpx.post(config.AI_GATEWAY_URL + '/generate', headers={'Authorization': 'Bearer ' + config.AI_GATEWAY_TOKEN}, json={'prompt': prompt, 'images': images or []}, timeout=480)
            if response.status_code in (401, 403, 429, 503):
                raise AIUnavailable(response.json().get('detail', '订阅暂不可用，请稍后重试'))
            response.raise_for_status()
            return response.json()['result']
        except (httpx.HTTPError, ValueError) as exc:
            raise AIUnavailable('AI 连接暂时不可用，内容已保留，可稍后重试') from exc
