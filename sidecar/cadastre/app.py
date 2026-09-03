"""The ASGI application. This is what you actually run.

`api.router` is an `APIRouter`, not an application. Uvicorn will happily start with a
router as its target - it is a Starlette `Router` and so is technically an ASGI
callable - and then answer **500 on every route**, because none of the request/response
machinery FastAPI installs around a router is present. It looks like a working server in
the logs and fails on the first request, which is why this module exists rather than
leaving the assembly to whoever reads the README.

    ./.venv/bin/python -m uvicorn cadastre.app:app --app-dir sidecar --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router

#: The desktop shell's Vite dev server (`tauri.conf.json` -> `devUrl`) and the viewer's.
#: Explicit origins rather than "*": the sidecar answers on localhost while a browser is
#: open on the same machine, and a wildcard would let any page the reviewer visits read
#: the project.
DEV_ORIGINS = [
    "http://localhost:1420", "http://127.0.0.1:1420",   # P1 desktop (Tauri devUrl)
    "http://localhost:5173", "http://127.0.0.1:5173",   # P5 viewer / Vite default
    "tauri://localhost",                                 # P1, packaged
]

app = FastAPI(
    title="groundup · cadastre",
    description="3D property units, ULPIN identity and topological validation (P4).",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
def index() -> dict[str, object]:
    """Name the block and point at the interesting routes.

    Enumerated from the router rather than from `app.routes`: recent FastAPI keeps an
    included router as one opaque entry there instead of flattening its routes, so
    filtering `app.routes` silently yields an empty list.
    """
    return {
        "block": "P4 · cadastre",
        "docs": "/docs",
        "routes": sorted({r.path for r in router.routes if hasattr(r, "path")}),
    }
