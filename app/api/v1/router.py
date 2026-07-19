from fastapi import APIRouter, HTTPException
from app.adapters.octoprint import OctoPrintAdapter
from app.services.stream_manager import StreamManager

def create_api_router(stream_manager: StreamManager, octoprint: OctoPrintAdapter) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    @router.get("/health")
    async def health() -> dict[str, str]: return {"status": "ok", "service": "PrintStream"}
    @router.get("/stream/status")
    async def stream_status() -> dict[str, object]: return stream_manager.status().to_dict()
    @router.post("/stream/start")
    async def stream_start() -> dict[str, object]:
        try: return (await stream_manager.start()).to_dict()
        except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    @router.post("/stream/stop")
    async def stream_stop() -> dict[str, object]: return (await stream_manager.stop()).to_dict()
    @router.get("/octoprint/status")
    async def octoprint_status() -> dict[str, object]: return await octoprint.get_status()
    return router
