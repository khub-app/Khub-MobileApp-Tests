import allure
import pytest
import yaml

from locators.login_locators import LoginLocators
from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage
from tests.base_test import BaseTest
from utilities.logger import get_logger

logger = get_logger(__name__)

with open("data/test_data.yaml", "r", encoding="utf-8") as f:
    TEST_DATA = yaml.safe_load(f)


@allure.feature("Login")
@allure.story("Admin app authentication")
class TestValidLogin(BaseTest):
    """The class-scoped `driver` fixture clears app data first, so this starts
    on the Login screen."""

    @pytest.mark.login
    def test_valid_login_lands_on_dashboard(self):
        creds = TEST_DATA["login"]["valid"]
        login = LoginPage(self.driver)
        assert login.is_loaded(), "Login screen did not render"

        login.login(creds["username"], creds["password"])

        assert login.is_login_successful(), "Dashboard did not load after valid login"
        assert DashboardPage(self.driver).is_loaded(), "Dashboard markers not all present"


@allure.feature("Login")
@allure.story("Login form validation")
class TestLoginValidation(BaseTest):
    @pytest.mark.login
    def test_empty_credentials_show_validation_errors(self):
        login = LoginPage(self.driver)
        assert login.is_loaded(), "Login screen did not render"

        login.click_login()

        assert login.is_displayed(LoginLocators.EMAIL_REQUIRED_ERROR, 10), \
            "Expected the email-required validation error"
        assert login.is_displayed(LoginLocators.PASSWORD_REQUIRED_ERROR, 10), \
            "Expected the password-required validation error"
