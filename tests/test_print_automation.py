from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.octoprint import OctoPrintAdapter
from app.config import Settings
from app.services.print_automation import PrintAutomation, is_print_active, is_printing
from app.services.stream_manager import StreamManager


def _status(
    *,
    connected: bool = True,
    printing: bool = False,
    paused: bool = False,
) -> dict:
    return {
        "connected": connected,
        "state": {
            "flags": {
                "printing": printing,
                "paused": paused,
                "pausing": False,
            },
            "text": "Printing" if printing else ("Paused" if paused else "Operational"),
        },
    }


def test_is_print_active_while_printing() -> None:
    assert is_print_active(_status(printing=True)) is True
    assert is_printing(_status(printing=True)) is True


def test_is_print_active_while_paused() -> None:
    assert is_print_active(_status(paused=True)) is True


def test_is_print_active_false_when_disconnected() -> None:
    assert is_print_active({"connected": False, "state": {"flags": {"printing": True}}}) is False


def test_is_print_active_false_when_idle() -> None:
    assert is_print_active(_status(printing=False)) is False


@pytest.mark.asyncio
async def test_baseline_does_not_start_or_stop() -> None:
    settings = Settings(auto_start_on_print=True, auto_stop_on_print_end=True)
    octoprint = MagicMock(spec=OctoPrintAdapter)
    octoprint.get_status = AsyncMock(return_value=_status(printing=True))
    stream_manager = MagicMock(spec=StreamManager)
    stream_manager.start = AsyncMock()
    stream_manager.stop = AsyncMock()

    automation = PrintAutomation(settings, octoprint, stream_manager)
    await automation.tick()

    stream_manager.start.assert_not_awaited()
    stream_manager.stop.assert_not_awaited()
    assert automation._was_printing is True


@pytest.mark.asyncio
async def test_rising_edge_starts_stream() -> None:
    settings = Settings(auto_start_on_print=True, auto_stop_on_print_end=False)
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
async def test_falling_edge_stops_stream() -> None:
    settings = Settings(auto_start_on_print=False, auto_stop_on_print_end=True)
    octoprint = MagicMock(spec=OctoPrintAdapter)
    octoprint.get_status = AsyncMock(
        side_effect=[_status(printing=True), _status(printing=False)]
    )
    stream_manager = MagicMock(spec=StreamManager)
    stream_manager.stop = AsyncMock()

    automation = PrintAutomation(settings, octoprint, stream_manager)
    await automation.tick()
    await automation.tick()

    stream_manager.stop.assert_awaited_once_with(user_requested=True)


@pytest.mark.asyncio
async def test_pause_does_not_stop_stream() -> None:
    settings = Settings(auto_start_on_print=False, auto_stop_on_print_end=True)
    octoprint = MagicMock(spec=OctoPrintAdapter)
    octoprint.get_status = AsyncMock(
        side_effect=[_status(printing=True), _status(paused=True)]
    )
    stream_manager = MagicMock(spec=StreamManager)
    stream_manager.stop = AsyncMock()

    automation = PrintAutomation(settings, octoprint, stream_manager)
    await automation.tick()
    await automation.tick()

    stream_manager.stop.assert_not_awaited()
    assert automation._was_printing is True


@pytest.mark.asyncio
async def test_disconnect_does_not_stop_stream() -> None:
    settings = Settings(auto_start_on_print=False, auto_stop_on_print_end=True)
    octoprint = MagicMock(spec=OctoPrintAdapter)
    octoprint.get_status = AsyncMock(
        side_effect=[
            _status(printing=True),
            {"connected": False, "error": "timeout"},
            _status(printing=True),
        ]
    )
    stream_manager = MagicMock(spec=StreamManager)
    stream_manager.stop = AsyncMock()

    automation = PrintAutomation(settings, octoprint, stream_manager)
    await automation.tick()
    await automation.tick()
    await automation.tick()

    stream_manager.stop.assert_not_awaited()
    assert automation._was_printing is True


@pytest.mark.asyncio
async def test_still_printing_does_not_restart() -> None:
    settings = Settings(auto_start_on_print=True, auto_stop_on_print_end=False)
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
async def test_start_disabled_when_both_off() -> None:
    settings = Settings(auto_start_on_print=False, auto_stop_on_print_end=False)
    automation = PrintAutomation(
        settings,
        MagicMock(spec=OctoPrintAdapter),
        MagicMock(spec=StreamManager),
    )
    await automation.start()
    assert automation.running is False


@pytest.mark.asyncio
async def test_start_runs_when_only_stop_enabled() -> None:
    settings = Settings(auto_start_on_print=False, auto_stop_on_print_end=True)
    automation = PrintAutomation(
        settings,
        MagicMock(spec=OctoPrintAdapter),
        MagicMock(spec=StreamManager),
    )
    await automation.start()
    assert automation.running is True
    await automation.stop()
