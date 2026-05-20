from fastapi import FastAPI
from .summits import router as summits_router
from .settings import router as settings_router
from .checks import router as checks_router

app = FastAPI(title="Paralert", version="0.1.0")

app.include_router(summits_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(checks_router, prefix="/api")
