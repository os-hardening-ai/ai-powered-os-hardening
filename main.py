from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.router_rag import router as rag_router
from api.router_chat import router as chat_router
from api.router_health import router as health_router
import uvicorn

def create_app() -> FastAPI:
    app = FastAPI(
        title="AI-Powered OS Hardening",
        version="0.2.0",
        description="CIS benchmark için RAG + LLM entegrasyonlu güvenlik hardening asistanı (Cohere + Qdrant + OpenAI/Groq).",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # RAG-only endpoint (backward compatibility)
    app.include_router(rag_router, prefix="/rag", tags=["rag"])

    # RAG + LLM combined endpoint (yeni!)
    app.include_router(chat_router, prefix="/api", tags=["chat"])

    # Health check
    app.include_router(health_router)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )
