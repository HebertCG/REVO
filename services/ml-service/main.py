from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from config import settings
from database import SessionLocal
from model.trainer import train_model, load_model
from routers.predict import router as predict_router
from routers.stats   import router as stats_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Al arrancar: entrenar el modelo si no existe."""
    if not os.path.exists(settings.MODEL_PATH):
        print("[REVO] Modelo no encontrado. Entrenando el Arbol de Decision...")
        db = SessionLocal()
        try:
            metrics = train_model(db)
            print(f"[REVO] Modelo entrenado OK: version={metrics['model_version']} "
                  f"acc={metrics['accuracy']*100:.1f}% "
                  f"depth={metrics['tree_depth']} leaves={metrics['n_leaves']}")
        except Exception as e:
            print(f"[REVO] Error al entrenar: {e}")
        finally:
            db.close()
    else:
        clf = load_model()
        print(f"[REVO] Modelo cargado desde disco (depth={clf.get_depth()}, leaves={clf.get_n_leaves()})")
    yield


app = FastAPI(
    title="REVO — ML Service",
    description="Microservicio de Machine Learning: Árbol de Decisión para recomendación de especialización.",
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

app.include_router(predict_router)
app.include_router(stats_router)


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "ml-service",
        "algorithm": "DecisionTreeClassifier",
        "status": "running",
        "model_path": settings.MODEL_PATH,
        "docs": "/docs"
    }

@app.get("/health", tags=["Health"])
def health():
    model_ready = os.path.exists(settings.MODEL_PATH)
    return {"status": "ok", "model_ready": model_ready}
