"""FastAPI router for the cadastre block, mounted by sidecar/app.py."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/cadastre", tags=["cadastre"])
