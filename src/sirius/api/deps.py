from __future__ import annotations

from fastapi import Header, HTTPException

from sirius.app import SiriusApp, get_app


def app_dep() -> SiriusApp:
    return get_app()


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_app().settings.sirius_api_key
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
