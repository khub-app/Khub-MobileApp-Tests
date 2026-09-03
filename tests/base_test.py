import pytest


class BaseTest:
    """Minimal base for admin-app tests.

    The class-scoped `driver` fixture (conftest.py) creates one Appium
    session per test class, clearing app data first so the class starts on
    the Login screen. This base just exposes it as `self.driver` for every
    test method. Inherit from this when a test only needs a raw session;
    build a dedicated *BaseSetup mixin (see the POS suite's POSBaseSetup)
    when a group of scenarios needs a shared logged-in precondition.
    """

    @pytest.fixture(autouse=True)
    def _wire_driver(self, request, driver):
        request.cls.driver = driver
