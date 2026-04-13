from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from routers.questions    import router as questions_router
from routers.sessions     import router as sessions_router
from routers.courses      import router as courses_router
from routers.jobs         import router as jobs_router
from routers.psychometric import router as psychometric_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="REVO — Survey Service",
    description="Microservicio de cuestionario: preguntas, sesiones y respuestas.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "https://revo-ilbm.vercel.app"],
    allow_origin_regex="https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(questions_router)
app.include_router(sessions_router)
app.include_router(courses_router)
app.include_router(jobs_router)
app.include_router(psychometric_router)


@app.get("/", tags=["Health"])
def root():
    return {"service": "survey-service", "status": "running", "version": "1.0.0"}

@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
