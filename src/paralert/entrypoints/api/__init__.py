import pathlib

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .summits import router as summits_router
from .settings import router as settings_router
from .checks import router as checks_router

STATIC_DIR = pathlib.Path(__file__).parent.parent / "static"

app = FastAPI(title="Paralert", version="0.1.0")

app.include_router(summits_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(checks_router, prefix="/api")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")
