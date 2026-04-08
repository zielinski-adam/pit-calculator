"""FastAPI application -- kalkulator PIT-38."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from pit38.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifecycle: log start/stop."""
    logger.info("PIT-38 Calculator API uruchomiony")
    yield
    logger.info("PIT-38 Calculator API zatrzymany")


def create_app() -> FastAPI:
    """Utwórz i skonfiguruj aplikację FastAPI."""
    app = FastAPI(
        title="PIT-38 Calculator",
        description="Kalkulator PIT-38 dla Interactive Brokers",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS -- frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api")

    return app


# Instancja dla uvicorn
app = create_app()
