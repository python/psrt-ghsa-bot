import pytest
import sentry_sdk


@pytest.fixture(scope="session", autouse=True)
def sentry_init():
    sentry_sdk.init(dsn=None, enable_tracing=False)
