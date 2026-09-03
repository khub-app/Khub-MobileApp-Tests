from locators.dashboard_locators import DashboardLocators
from locators.login_locators import LoginLocators
from pages.base_page import BasePage
from utilities.logger import get_logger

logger = get_logger(__name__)


class LoginPage(BasePage):
    def enter_username(self, username: str):
        logger.info("Entering username")
        self.type_text(LoginLocators.USERNAME_INPUT, username)
        return self

    def enter_password(self, password: str):
        logger.info("Entering password")
        self.type_text(LoginLocators.PASSWORD_INPUT, password)
        return self

    def click_login(self):
        logger.info("Tapping Login")
        self.hide_keyboard()
        self.click(LoginLocators.LOGIN_BUTTON)
        return self

    def login(self, username: str, password: str):
        self.dismiss_system_anr_if_present()
        self.enter_username(username)
        self.enter_password(password)
        self.click_login()
        return self

    def is_loaded(self, timeout: int = 20) -> bool:
        return self.is_displayed(LoginLocators.WELCOME_HEADER, timeout)

    def is_login_successful(self, timeout: int = 60) -> bool:
        """Login lands on the Dashboard. The backend round-trip on a loaded
        emulator can take 30s+, so this waits generously."""
        return self.is_displayed(DashboardLocators.TITLE, timeout)
