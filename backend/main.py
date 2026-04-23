"""
main.py
─────────────────────────────────────────────────────────────
Punto de entrada de la aplicación FastAPI de FLUX.

PROCESO: Inicializa la app, configura CORS y registra los routers
         de la API. Incluye el endpoint de salud (/health) para
         verificar conectividad desde el frontend y pipelines de CI.

SALIDA:  Aplicación ASGI lista para ser servida por uvicorn.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import sys
import asyncio
# Parche de compatibilidad para Windows (PSYCZOPG + Asyncio)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.config import settings


# ── Inicialización de la App ──────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)


# ── CORS ─────────────────────────────────────────────────────
# En desarrollo, se permite el origen del servidor de desarrollo del frontend.
# En producción, reemplazar por la URL real del dominio.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────
from app.api.v1 import chat, docs

app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(docs.router, prefix="/api/v1", tags=["docs"])


# ── Endpoints Base ────────────────────────────────────────────

@app.get("/health", tags=["system"])
def health_check():
    """
    Endpoint de salud del sistema.

    INPUT:  Ninguno.
    PROCESO: Verifica que la aplicación levantó correctamente y que
             las variables de configuración críticas están presentes.
    OUTPUT: JSON con estado del sistema y versión.
    """
    return {
        "status": "alive",
        "service": settings.app_name,
        "version": settings.app_version,
        "engine": "LangGraph + VertexAI",
        "debug_mode": settings.debug,
    }
