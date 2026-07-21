from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.octoprint import OctoPrintAdapter
from app.config import Settings
from app.services.print_automation import PrintAutomation, is_printing
from app.services.stream_manager import StreamManager


def _status(*, connected: bool = True, printing: bool = False) -> dict:
    return {
        "connected": connected,
        "state": {"flags": {"printing": printing}, "text": "Printing" if printing else "Operational"},
    }


def test_is_printing_true() -> None:
    assert is_printing(_status(printing=True)) is True


def test_is_printing_false_when_disconnected() -> None:
    assert is_printing({"connected": False, "state": {"flags": {"printing": True}}}) is False


def test_is_printing_false_when_idle() -> None:
    assert is_printing(_status(printing=False)) is False


@pytest.mark.asyncio
async def test_baseline_does_not_start_stream() -> None:
    settings = Settings(auto_start_on_print=True, auto_print_poll_seconds=10)
    octoprint = MagicMock(spec=OctoPrintAdapter)
    octoprint.get_status = AsyncMock(return_value=_status(printing=True))
    stream_manager = MagicMock(spec=StreamManager)
    stream_manager.start = AsyncMock()

    automation = PrintAutomation(settings, octoprint, stream_manager)
    await automation.tick()

    stream_manager.start.assert_not_awaited()
    assert automation._was_printing is True


@pytest.mark.asyncio
async def test_rising_edge_starts_stream() -> None:
    settings = Settings(auto_start_on_print=True, auto_print_poll_seconds=10)
    octoprint = MagicMock(spec=OctoPrintAdapter)
    octoprint.get_status = AsyncMock(
        side_effect=[_status(printing=False), _status(printing=True)]
    )
    stream_manager = MagicMock(spec=StreamManager)
    stream_manager.start = AsyncMock()

    automation = PrintAutomation(settings, octoprint, stream_manager)
    await automation.tick()
    await automation.tick()

    stream_manager.start.assert_awaited_once_with(user_requested=True)


@pytest.mark.asyncio
async def test_still_printing_does_not_restart() -> None:
    settings = Settings(auto_start_on_print=True, auto_print_poll_seconds=10)
    octoprint = MagicMock(spec=OctoPrintAdapter)
    octoprint.get_status = AsyncMock(
        side_effect=[
            _status(printing=False),
            _status(printing=True),
            _status(printing=True),
        ]
    )
    stream_manager = MagicMock(spec=StreamManager)
    stream_manager.start = AsyncMock()

    automation = PrintAutomation(settings, octoprint, stream_manager)
    await automation.tick()
    await automation.tick()
    await automation.tick()

    stream_manager.start.assert_awaited_once_with(user_requested=True)


@pytest.mark.asyncio
async def test_start_disabled_does_nothing() -> None:
    settings = Settings(auto_start_on_print=False)
    automation = PrintAutomation(
        settings,
        MagicMock(spec=OctoPrintAdapter),
        MagicMock(spec=StreamManager),
    )
    await automation.start()
    assert automation.running is False
