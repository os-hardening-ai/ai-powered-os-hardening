from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes_rag import router as rag_router
from api.router_health import router as health_router
import uvicorn

def create_app() -> FastAPI:
    app = FastAPI(
        title="OS Hardening RAG",
        version="0.1.0",
        description="CIS Ubuntu 24.04 benchmark için RAG retrieval servisi (Cohere + Qdrant).",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(rag_router ,prefix="/rag", tags=["rag"])
    app.include_router(health_router)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )
