"""FastAPI router for the cadastre block.

Exposed as a router rather than an app so the host process can mount it wherever it
likes. This package makes no assumption about what that host is or where it lives.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/cadastre", tags=["cadastre"])
