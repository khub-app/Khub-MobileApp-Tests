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
        """The Login button can take well over 60s to become clickable on the
        very first Appium session of a fresh pytest process (confirmed live
        2026-10-21 against the Oct-20 APK build - a cold UiAutomator2/app
        session is measurably slower than a 2nd+ session in the same run),
        so this waits longer than BasePage.click's 60s default."""
        logger.info("Tapping Login")
        self.hide_keyboard()
        self.click(LoginLocators.LOGIN_BUTTON, timeout=120)
        return self

    def login(self, username: str, password: str):
        # An ANR from an unrelated app sharing this emulator (e.g. the POS
        # app crash-looping) can pop up at any point, not just at launch -
        # confirmed live 2026-10-21: it appeared mid-login and silently
        # blocked every subsequent tap/type until dismissed. So this checks
        # before each step, not just once up front.
        self.dismiss_system_anr_if_present()
        self.enter_username(username)
        self.dismiss_system_anr_if_present()
        self.enter_password(password)
        self.dismiss_system_anr_if_present()
        self.click_login()
        return self

    def is_loaded(self, timeout: int = 20) -> bool:
        return self.is_displayed(LoginLocators.WELCOME_HEADER, timeout)

    def is_login_successful(self, timeout: int = 60) -> bool:
        """Login lands on the Dashboard. The backend round-trip on a loaded
        emulator can take 30s+, so this waits generously."""
        return self.is_displayed(DashboardLocators.TITLE, timeout)
