from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from .auth import bootstrap_invite, router as auth_router
from .nodes import router as nodes_router
from .ai import router as ai_router
from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bootstrap_invite()
    yield


app = FastAPI(title="生长 Growth API", version="0.1.0", lifespan=lifespan)
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


@app.middleware("http")
async def origin_guard(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != config.APP_ORIGIN:
            return JSONResponse({"detail": "请求来源无效"}, status_code=403)
    return await call_next(request)


@app.get("/api/health")
def health():
    return {"status": "ok"}
