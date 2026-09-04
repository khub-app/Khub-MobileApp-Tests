import pytest
import yaml

from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage

with open("data/test_data.yaml", "r", encoding="utf-8") as f:
    TEST_DATA = yaml.safe_load(f)


class MobileBaseSetup:
    """Reusable precondition for admin-app scenario tests: log in once per
    class and expose `self.driver` + `self.dashboard` to every test method.

    Mirrors khub-pos-tests' POSBaseSetup, minus the clock-in / switch-user
    stages (the admin app has no shift concept). Inherit from this instead
    of BaseTest whenever a class-scoped scenario needs to start logged in on
    the Dashboard.
    """

    @pytest.fixture(autouse=True, scope="class")
    def _mobile_base_setup(self, request, driver):
        creds = TEST_DATA["login"]["valid"]

        login_page = LoginPage(driver)
        login_page.login(creds["username"], creds["password"])
        assert login_page.is_login_successful(timeout=90), "Login precondition failed"

        dashboard = DashboardPage(driver)
        assert dashboard.is_loaded(), "Dashboard did not load after login"

        request.cls.driver = driver
        request.cls.dashboard = dashboard
