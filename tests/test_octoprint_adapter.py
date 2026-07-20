from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.octoprint import OctoPrintAdapter
from app.config import Settings


@pytest.mark.asyncio
async def test_get_status_merges_display_layer_progress() -> None:
    adapter = OctoPrintAdapter(
        Settings(octoprint_base_url="http://octo", octoprint_api_key="key")
    )

    printer_response = MagicMock()
    printer_response.raise_for_status = MagicMock()
    printer_response.json.return_value = {
        "state": {"text": "Printing"},
        "temperature": {},
    }

    job_response = MagicMock()
    job_response.raise_for_status = MagicMock()
    job_response.json.return_value = {
        "job": {"file": {"name": "a.gcode"}},
        "progress": {"completion": 10.0, "printTimeLeft": 100},
    }

    layer_response = MagicMock()
    layer_response.status_code = 200
    layer_response.json.return_value = {
        "layer": {"current": "7", "total": "42"},
    }

    client = AsyncMock()
    client.get = AsyncMock(
        side_effect=[printer_response, job_response, layer_response]
    )
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.adapters.octoprint.httpx.AsyncClient", return_value=client):
        status = await adapter.get_status()

    assert status["connected"] is True
    assert status["progress"]["currentLayer"] == "7"
    assert status["progress"]["totalLayer"] == "42"
    assert status["progress"]["completion"] == 10.0


@pytest.mark.asyncio
async def test_get_status_works_without_layer_plugin() -> None:
    adapter = OctoPrintAdapter(
        Settings(octoprint_base_url="http://octo", octoprint_api_key="key")
    )

    printer_response = MagicMock()
    printer_response.raise_for_status = MagicMock()
    printer_response.json.return_value = {"state": {}, "temperature": {}}

    job_response = MagicMock()
    job_response.raise_for_status = MagicMock()
    job_response.json.return_value = {"job": {}, "progress": {"completion": 1.0}}

    layer_response = MagicMock()
    layer_response.status_code = 404

    client = AsyncMock()
    client.get = AsyncMock(
        side_effect=[printer_response, job_response, layer_response]
    )
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.adapters.octoprint.httpx.AsyncClient", return_value=client):
        status = await adapter.get_status()

    assert status["connected"] is True
    assert "currentLayer" not in status["progress"]
