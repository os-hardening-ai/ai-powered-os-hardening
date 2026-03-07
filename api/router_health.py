from __future__ import annotations
from fastapi import APIRouter


router = APIRouter()


@router.get("/health", tags=["system"])
async def health_check() -> dict:
    return {"status": "ok"}

@router.get("/")
async def root() -> dict:
    return {"message": "Welcome to the OS Hardening RAG API!"}