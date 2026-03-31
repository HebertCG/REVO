from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from database import engine, Base
from routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crear tablas si no existen (por si se usa sin Docker)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="REVO — Auth Service",
    description="Microservicio de autenticación: registro, login y gestión de usuarios.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — permitir peticiones del frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas
app.include_router(auth_router)


@app.get("/", tags=["Health"])
def root():
    return {
        "service": settings.SERVICE_NAME,
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
