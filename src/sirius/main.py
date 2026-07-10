from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from sirius import __version__
from sirius.api.routes import router
from sirius.app import get_app
from sirius.tasks.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_app()  # build all components eagerly
    start_scheduler()
    yield


def create_api() -> FastAPI:
    api = FastAPI(title="Sirius", version=__version__, lifespan=lifespan)
    api.include_router(router)
    return api


app = create_api()


if __name__ == "__main__":
    import uvicorn

    settings = get_app().settings
    uvicorn.run("sirius.main:app", host=settings.host, port=settings.port)
