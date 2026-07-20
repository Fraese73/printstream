import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.adapters.octoprint import OctoPrintAdapter
from app.api.v1.router import create_api_router
from app.config import get_settings
from app.services.stream_manager import StreamManager

settings = get_settings()
stream_manager = StreamManager(settings)
octoprint = OctoPrintAdapter(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Nach Reboot: gewünschten Stream wieder aufnehmen, ohne den Start zu blockieren.
    resume_task = asyncio.create_task(stream_manager.resume_if_desired())
    try:
        yield
    finally:
        resume_task.cancel()
        # Herunterfahren (z. B. nächtlicher Reboot) darf den Wunschzustand nicht löschen.
        await stream_manager.stop(user_requested=False)


app = FastAPI(title="PrintStream", version="0.1.0", lifespan=lifespan)
app.include_router(create_api_router(stream_manager, octoprint))
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html", context={})
