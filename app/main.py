import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.octoprint_client import OctoPrintClient
from app.overlay import OverlayWriter
from app.stream_manager import StreamManager

settings = get_settings()
stream_manager = StreamManager(settings)
octoprint_client = OctoPrintClient(settings)
overlay_writer = OverlayWriter(
    settings=settings,
    octoprint_client=octoprint_client,
    overlay_path=stream_manager.overlay_path,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await overlay_writer.stop()
    await stream_manager.stop()


app = FastAPI(title="PrintStream", version="0.2.0", lifespan=lifespan)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"stream": stream_manager.status()},
    )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "PrintStream",
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "stream_running": stream_manager.status().running,
    }


@app.get("/api/stream/status")
async def stream_status():
    return stream_manager.status()


@app.post("/api/stream/start")
async def stream_start():
    status = await stream_manager.start()
    if status.running:
        await overlay_writer.start()
    return status


@app.post("/api/stream/stop")
async def stream_stop():
    await overlay_writer.stop()
    return await stream_manager.stop()


@app.get("/api/octoprint/status")
async def octoprint_status():
    return await octoprint_client.get_printer_status()
