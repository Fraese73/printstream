from typing import Any
import httpx
from app.config import Settings

class OctoPrintAdapter:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.octoprint_base_url.rstrip("/")
        self.api_key = settings.octoprint_api_key

    async def get_status(self) -> dict[str, Any]:
        if not self.api_key:
            return {"connected": False, "error": "Kein OctoPrint-API-Key konfiguriert."}
        headers = {"X-Api-Key": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                printer_response = await client.get(f"{self.base_url}/api/printer", headers=headers)
                job_response = await client.get(f"{self.base_url}/api/job", headers=headers)
            printer_response.raise_for_status(); job_response.raise_for_status()
            printer = printer_response.json(); job = job_response.json()
            return {"connected": True, "state": printer.get("state", {}), "temperature": printer.get("temperature", {}), "job": job.get("job", {}), "progress": job.get("progress", {})}
        except Exception as exc:
            return {"connected": False, "error": str(exc)}
