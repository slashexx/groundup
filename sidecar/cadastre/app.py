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

import sqlite3

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import router
from .store import ProjectIncomplete
from .ulpin import encode, ledger

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


# --- refusals that read as refusals ---------------------------------------------------
#
# A guard that fires correctly still owes the caller a readable answer. Several routes
# reach a database that is not a project, or an identifier space that is full, and the
# uncaught exception became a 500 with a stack trace - which reads as "the server is
# broken", not "this file is not a project" or "this parcel has no numbers left". The
# operator's next action is completely different in each case.
#
# Registered on the app rather than added to each handler because the next route added
# would not have them, and the failure is silent until someone hits it.

@app.exception_handler(ProjectIncomplete)
def _incomplete(_: Request, exc: ProjectIncomplete) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(encode.SequenceExhausted)
def _exhausted(_: Request, exc: encode.SequenceExhausted) -> JSONResponse:
    #: 409, not 500: the request is well formed and the register is full. Nothing the
    #: caller retries will help, and the fix is a different parent parcel.
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ledger.UnknownParcel)
@app.exception_handler(ledger.AlreadyIssued)
def _ledger(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(sqlite3.OperationalError)
def _operational(_: Request, exc: sqlite3.OperationalError) -> JSONResponse:
    message = str(exc)
    if "no such table" in message.lower():
        return JSONResponse(status_code=422, content={"detail": (
            f"{message}. This database is missing a table this block needs, so it is "
            "either not a cadastre project or a step that builds it has not run. Check "
            "the path first.")})
    if "locked" in message.lower():
        return JSONResponse(status_code=409, content={"detail": (
            f"{message}. Another process is writing to this project. Close it and retry.")})
    return JSONResponse(status_code=422, content={"detail": message})


@app.exception_handler(sqlite3.DatabaseError)
def _not_a_database(_: Request, exc: sqlite3.DatabaseError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": (
        f"{exc}. The file at this path is not a readable database.")})


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
