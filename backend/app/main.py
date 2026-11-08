from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.companion.models  # noqa: F401  (registers tables on Base.metadata)
from app.companion.errors import register_error_handlers
from app.companion.router import router as companion_router
from app.core.config import get_settings
from app.core.db import Base, dispose_engine, get_engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Dev/week-1 schema bootstrap. Alembic migrations come later.
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await dispose_engine()


app = FastAPI(title="Aira Companion", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(companion_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
