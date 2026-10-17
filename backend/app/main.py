from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, brief, campaigns, health, impact, me, plan, posts
from app.api import config as config_api
from app.api.deps import install_ai
from app.core.config import Settings, get_settings
from app.core.errors import AppError, install_error_handlers
from app.core.middleware import install_middleware
from app.db.session import install_database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Campaory",
        docs_url=None if settings.is_production else "/api/docs",
        openapi_url=None if settings.is_production else "/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings
    install_error_handlers(app)
    install_database(app, settings.database_url)
    auth.install(app, settings)
    install_ai(app, settings)
    install_middleware(app, settings)

    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(auth.router_for(settings))
    api.include_router(me.router)
    api.include_router(campaigns.router)
    for module in (config_api, brief, plan, posts, impact):
        api.include_router(module.router)

    @api.api_route(
        "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], include_in_schema=False
    )
    def api_not_found(path: str) -> None:
        raise AppError(404, "not_found", "No such endpoint.")

    app.include_router(api)
    _mount_spa(app, Path(settings.static_dir))
    return app


def _mount_spa(app: FastAPI, static_dir: Path) -> None:
    index = static_dir / "index.html"
    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    root = static_dir.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = (static_dir / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index)
        raise AppError(404, "not_found", "Frontend not built.")


app = create_app()
