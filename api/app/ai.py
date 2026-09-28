import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator

from . import config
from .common import owned_node
from .common import add_event
from .db import connect, transaction
from .security import decrypt_key, encrypt_key, iso, require_user

router = APIRouter(prefix="/api/ai")


class KeyInput(BaseModel):
    api_key: str = Field(min_length=10, max_length=256)


class AIInput(BaseModel):
    action: str
    node_ids: list[str] = Field(min_length=1, max_length=20)
    instruction: str = Field(default="", max_length=1000)


class SuggestedTask(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    note: str = Field(default="", max_length=500)
    due_on: str | None = None

    @field_validator("due_on")
    @classmethod
    def validate_due_on(cls, value):
        if value is not None:
            datetime.strptime(value, "%Y-%m-%d")
        return value


class AIResult(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    suggestions: list[SuggestedTask] = Field(default_factory=list, max_length=8)


class ReviewInput(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)


@router.get("/key")
def key_status(user=Depends(require_user)):
    with connect() as db:
        row = db.execute("SELECT suffix,updated_at FROM ai_keys WHERE user_id=?", (user["id"],)).fetchone()
    return {"configured": bool(row), "suffix": row["suffix"] if row else None, "updated_at": row["updated_at"] if row else None}


@router.put("/key")
def save_key(data: KeyInput, user=Depends(require_user)):
    value = data.api_key.strip()
    encrypted = encrypt_key(value)
    with transaction() as db:
        db.execute("INSERT INTO ai_keys VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET ciphertext=excluded.ciphertext,suffix=excluded.suffix,updated_at=excluded.updated_at", (user["id"], encrypted, value[-4:], iso()))
    return {"configured": True, "suffix": value[-4:]}


@router.delete("/key", status_code=204)
def delete_key(user=Depends(require_user)):
    with transaction() as db:
        db.execute("DELETE FROM ai_keys WHERE user_id=?", (user["id"],))


def acquire_slot(user):
    day = datetime.now(ZoneInfo(user["timezone"])).date().isoformat()
    with transaction() as db:
        db.execute("INSERT OR IGNORE INTO ai_usage(user_id,day,count,busy) VALUES(?,?,0,0)", (user["id"], day))
        row = db.execute("SELECT count,busy FROM ai_usage WHERE user_id=? AND day=?", (user["id"], day)).fetchone()
        if row["count"] >= config.AI_DAILY_LIMIT:
            raise HTTPException(429, "今天的 AI 调用次数已用完")
        if row["busy"]:
            raise HTTPException(429, "已有一项 AI 请求正在进行")
        db.execute("UPDATE ai_usage SET count=count+1,busy=1 WHERE user_id=? AND day=?", (user["id"], day))
    return day


def release_slot(user_id, day):
    with transaction() as db:
        db.execute("UPDATE ai_usage SET busy=0 WHERE user_id=? AND day=?", (user_id, day))


@router.post("/suggest")
def suggest(data: AIInput, user=Depends(require_user)):
    if data.action not in ("decompose", "review", "align"):
        raise HTTPException(422, "AI 操作无效")
    with connect() as db:
        key_row = db.execute("SELECT ciphertext FROM ai_keys WHERE user_id=?", (user["id"],)).fetchone()
        if not key_row:
            raise HTTPException(400, "请先设置 DeepSeek API Key")
        context = []
        for node_id in dict.fromkeys(data.node_ids):
            node = owned_node(db, user["id"], node_id)
            selected = {key: node[key] for key in ("id", "kind", "title", "note", "starts_on", "ends_on", "due_on", "is_done")}
            selected["note"] = selected["note"][:1000]
            context.append(selected)
    key = decrypt_key(key_row["ciphertext"])
    day = acquire_slot(user)
    try:
        prompt = {
            "action": data.action,
            "goals": context,
            "user_instruction": data.instruction,
            "output_schema": {"summary": "简短中文说明", "suggestions": [{"title": "可执行任务", "note": "简短说明", "due_on": "YYYY-MM-DD 或 null"}]},
        }
        with httpx.Client(timeout=35) as client:
            response = client.post(
                f"{config.DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": config.DEEPSEEK_MODEL, "max_tokens": 1200,
                      "response_format": {"type": "json_object"},
                      "messages": [
                          {"role": "system", "content": "你是大学生成长规划助手。只输出符合给定结构的 json，不要执行或声称已修改任务。建议要具体、简短、可完成。"},
                          {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                      ]},
            )
        if response.status_code == 401:
            raise HTTPException(400, "DeepSeek API Key 无效")
        if response.status_code == 429:
            raise HTTPException(429, "DeepSeek 暂时限流，请稍后重试")
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if not content:
            raise ValueError("empty AI content")
        result = AIResult.model_validate(json.loads(content))
        return {"summary": result.summary, "suggestions": [x.model_dump() for x in result.suggestions], "saved": False}
    except (ValueError, KeyError, IndexError, ValidationError):
        raise HTTPException(502, "AI 返回的内容无法使用，请重试")
    except httpx.HTTPError:
        raise HTTPException(502, "暂时无法连接 DeepSeek，请稍后重试")
    finally:
        release_slot(user["id"], day)


@router.get("/usage")
def usage(user=Depends(require_user)):
    day = datetime.now(ZoneInfo(user["timezone"])).date().isoformat()
    with connect() as db:
        row = db.execute("SELECT count FROM ai_usage WHERE user_id=? AND day=?", (user["id"], day)).fetchone()
    return {"day": day, "used": row["count"] if row else 0, "limit": config.AI_DAILY_LIMIT}


@router.post("/review")
def save_review(data: ReviewInput, user=Depends(require_user)):
    with transaction() as db:
        add_event(db, user["id"], None, "review_saved", {"summary": data.summary})
    return {"message": "复盘已保存"}
