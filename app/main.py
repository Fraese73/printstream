import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.adapters.octoprint import OctoPrintAdapter
from app.api.v1.router import create_api_router
from app.config import get_settings
from app.services.overlay import OverlayWriter
from app.services.stream_manager import StreamManager

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
octoprint = OctoPrintAdapter(settings)
stream_manager = StreamManager(settings)
overlay_writer = OverlayWriter(
    settings=settings,
    octoprint=octoprint,
    overlay_path=stream_manager.overlay_path,
)
stream_manager.overlay = overlay_writer


@asynccontextmanager
async def lifespan(_app: FastAPI):
    resume_task = asyncio.create_task(stream_manager.resume_if_desired())
    try:
        yield
    finally:
        resume_task.cancel()
        await stream_manager.stop(user_requested=False)


app = FastAPI(title="PrintStream", version="0.1.0", lifespan=lifespan)
app.include_router(create_api_router(stream_manager, octoprint))
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html", context={})
