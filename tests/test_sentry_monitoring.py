from unittest import mock

import pytest

from psrt_ghsa_bot import _sentry_monitoring as sm
from psrt_ghsa_bot import app


@pytest.mark.parametrize("dsn", [None, "https://public@o0.ingest.sentry.io/0"])
def test_init_with_dsn(monkeypatch, dsn) -> None:
    if dsn:
        monkeypatch.setenv("SENTRY_DSN", dsn)
    else:
        monkeypatch.delenv("SENTRY_DSN", raising=False)
    with mock.patch.object(sm.sentry_sdk, "init") as init:
        sm.init_sentry()
    init.assert_called_once()
    assert init.call_args.kwargs["dsn"] == dsn


def test_main_reports_ok_on_success() -> None:
    with (
        mock.patch("psrt_ghsa_bot.app.init_sentry") as init,
        mock.patch("psrt_ghsa_bot.app.run") as run,
        mock.patch("sentry_sdk.crons.capture_checkin", return_value="cid") as capture,
    ):
        app.main()

    init.assert_called_once()
    run.assert_called_once()
    assert [c.kwargs["status"] for c in capture.call_args_list] == [sm.STATUS_IN_PROGRESS, sm.STATUS_OK]
    assert capture.call_args_list[-1].kwargs["check_in_id"] == "cid"


def test_main_reports_error_and_reraises() -> None:
    with (
        mock.patch("psrt_ghsa_bot.app.init_sentry"),
        mock.patch("psrt_ghsa_bot.app.run", side_effect=RuntimeError("uh oh")),
        mock.patch("sentry_sdk.crons.capture_checkin", return_value="cid") as capture,
    ):
        with pytest.raises(RuntimeError, match="uh oh"):
            app.main()

    assert [c.kwargs["status"] for c in capture.call_args_list] == [sm.STATUS_IN_PROGRESS, sm.STATUS_ERROR]
    assert capture.call_args_list[-1].kwargs["check_in_id"] == "cid"


def test_main_runs_on_checkin_error() -> None:
    with (
        mock.patch("psrt_ghsa_bot.app.init_sentry") as init,
        mock.patch("psrt_ghsa_bot.app.run") as run,
        mock.patch("sentry_sdk.crons.capture_checkin", side_effect=AttributeError) as capture,
    ):
        app.main()

    init.assert_called_once()
    run.assert_called_once()
    capture.assert_called_once()
