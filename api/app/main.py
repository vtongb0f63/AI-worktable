from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from .auth import bootstrap_invite, router as auth_router
from .nodes import router as nodes_router
from .ai import router as ai_router
from .db import init_db
from .planner.router import router as planner_router
from .planner.domain import Conflict
from pydantic import ValidationError


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bootstrap_invite()
    yield


app = FastAPI(title="日课 Personal Study API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.APP_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(auth_router)
app.include_router(nodes_router)
app.include_router(ai_router)
app.include_router(planner_router)


@app.exception_handler(Conflict)
async def conflict_handler(request, exc):
    return JSONResponse({'detail': str(exc), 'code': 'conflict'}, status_code=409)


@app.exception_handler(ValidationError)
async def validation_handler(request, exc):
    return JSONResponse({'detail': '；'.join(str(e['msg']) for e in exc.errors()[:5]), 'code': 'validation'}, status_code=422)


@app.exception_handler(ValueError)
async def value_handler(request, exc):
    return JSONResponse({'detail': str(exc), 'code': 'validation'}, status_code=422)


@app.exception_handler(KeyError)
async def missing_handler(request, exc):
    return JSONResponse({'detail': '记录不存在或无权访问', 'code': 'not_found'}, status_code=404)


@app.middleware("http")
async def origin_guard(request: Request, call_next):
    if config.PRIVATE_MODE and request.method != 'GET' and (request.url.path.startswith('/api/nodes') or request.url.path.startswith('/api/weeks/') or request.url.path.startswith('/api/admin/') or request.url.path == '/api/reports'):
        return JSONResponse({'detail': '历史目标仅供查阅'}, status_code=403)
    if config.PRIVATE_MODE and (request.url.path.startswith('/api/public/') or request.url.path.startswith('/api/ai/') or request.url.path in ('/api/admin/invites', '/api/auth/resend-verification')):
        return JSONResponse({'detail': '此功能在个人工作台中已关闭'}, status_code=404)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != config.APP_ORIGIN:
            return JSONResponse({"detail": "请求来源无效"}, status_code=403)
    return await call_next(request)


@app.get("/api/health")
def health():
    return {"status": "ok"}
