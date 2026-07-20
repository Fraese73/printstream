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
                printer_response = await client.get(
                    f"{self.base_url}/api/printer", headers=headers
                )
                job_response = await client.get(
                    f"{self.base_url}/api/job", headers=headers
                )
                layer_data = await self._fetch_layer_progress(client, headers)
            printer_response.raise_for_status()
            job_response.raise_for_status()
            printer = printer_response.json()
            job = job_response.json()
            progress = job.get("progress", {}) or {}
            if layer_data:
                progress = {**progress, **layer_data}
            return {
                "connected": True,
                "state": printer.get("state", {}),
                "temperature": printer.get("temperature", {}),
                "job": job.get("job", {}),
                "progress": progress,
            }
        except Exception as exc:
            return {"connected": False, "error": str(exc)}

    async def _fetch_layer_progress(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Layer kommt nicht aus der Standard-API, sondern oft aus DisplayLayerProgress."""
        try:
            response = await client.get(
                f"{self.base_url}/plugin/DisplayLayerProgress/values",
                headers=headers,
            )
            if response.status_code != 200:
                return {}
            payload = response.json()
        except Exception:
            return {}

        layer = payload.get("layer") if isinstance(payload, dict) else None
        if not isinstance(layer, dict):
            return {}

        result: dict[str, Any] = {}
        if layer.get("current") is not None:
            result["currentLayer"] = layer.get("current")
        if layer.get("total") is not None:
            result["totalLayer"] = layer.get("total")
        return result
