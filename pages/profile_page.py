from locators.profile_locators import ProfileLocators as L
from pages.base_page import BasePage
from utilities.logger import get_logger

logger = get_logger(__name__)


class ProfilePage(BasePage):
    """Profile screen, reached via DashboardPage.open_profile()."""

    def is_loaded(self, timeout: int = 20) -> bool:
        return self.is_displayed(L.TITLE, timeout)

    def go_to_label_management(self):
        from pages.label_management_page import LabelManagementPage

        logger.info("Navigating to Label Management")
        self.click(L.LABEL_MANAGEMENT)
        page = LabelManagementPage(self.driver)
        assert page.is_loaded(), "Label Management page did not open"
        return page
