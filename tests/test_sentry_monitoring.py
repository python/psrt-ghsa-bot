from unittest import mock

import pytest

from psrt_ghsa_bot import _sentry_monitoring as sm
from psrt_ghsa_bot import app

DSN = "https://public@o0.ingest.sentry.io/0"


def test_noop_without_dsn(monkeypatch) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    with mock.patch.object(sm.sentry_sdk, "init") as init:
        sm.init_sentry()
    init.assert_not_called()

    with mock.patch.object(sm.crons, "capture_checkin") as capture:
        result = sm.capture_checkin(sm.MONITOR_SLUG_GHSA, sm.STATUS_OK)
    assert result is None
    capture.assert_not_called()


def test_init_with_dsn(monkeypatch) -> None:
    monkeypatch.setenv("SENTRY_DSN", DSN)
    with mock.patch.object(sm.sentry_sdk, "init") as init:
        sm.init_sentry()
    init.assert_called_once()
    assert init.call_args.kwargs["dsn"] == DSN


def test_capture_checkin_with_dsn(monkeypatch) -> None:
    monkeypatch.setenv("SENTRY_DSN", DSN)
    with mock.patch.object(sm.crons, "capture_checkin", return_value="stanstan") as capture:
        result = sm.capture_checkin(sm.MONITOR_SLUG_GHSA, sm.STATUS_OK, duration=1.5, check_in_id="stanstan")
    assert result == "stanstan"
    capture.assert_called_once_with(
        monitor_slug=sm.MONITOR_SLUG_GHSA,
        status=sm.STATUS_OK,
        duration=1.5,
        check_in_id="stanstan",
    )


def test_capture_checkin_swallow_sdk_errors(monkeypatch) -> None:
    monkeypatch.setenv("SENTRY_DSN", DSN)
    with mock.patch.object(sm.crons, "capture_checkin", side_effect=AttributeError):
        assert sm.capture_checkin(sm.MONITOR_SLUG_GHSA, sm.STATUS_OK) is None


def test_main_reports_ok_on_success() -> None:
    with (
        mock.patch("psrt_ghsa_bot.app.init_sentry") as init,
        mock.patch("psrt_ghsa_bot.app.run") as run,
        mock.patch("psrt_ghsa_bot.app.capture_checkin", return_value="cid") as capture,
    ):
        app.main()

    init.assert_called_once()
    run.assert_called_once()
    assert [c.args[1] for c in capture.call_args_list] == [app.STATUS_IN_PROGRESS, app.STATUS_OK]
    assert capture.call_args_list[-1].kwargs["check_in_id"] == "cid"


def test_main_reports_error_and_reraises() -> None:
    with (
        mock.patch("psrt_ghsa_bot.app.init_sentry"),
        mock.patch("psrt_ghsa_bot.app.run", side_effect=RuntimeError("uh oh")),
        mock.patch("psrt_ghsa_bot.app.capture_checkin", return_value="cid") as capture,
    ):
        with pytest.raises(RuntimeError, match="uh oh"):
            app.main()

    assert [c.args[1] for c in capture.call_args_list] == [app.STATUS_IN_PROGRESS, app.STATUS_ERROR]
    assert capture.call_args_list[-1].kwargs["check_in_id"] == "cid"
