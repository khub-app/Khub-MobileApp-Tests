from locators.dashboard_locators import DashboardLocators
from locators.nav_drawer_locators import NavDrawerLocators
from pages.base_page import BasePage
from utilities.logger import get_logger

logger = get_logger(__name__)


class NavDrawerPage(BasePage):
    """The left navigation drawer. `open()` taps the header hamburger; the
    individual go_* helpers open it first, so tests can just call those."""

    def open(self):
        logger.info("Opening navigation drawer")
        self.click(NavDrawerLocators.HAMBURGER)
        self.find(NavDrawerLocators.SALES_HISTORY, timeout=10)
        return self

    def _go(self, locator, page_cls, *marker):
        self.open()
        self.click(locator)
        page = page_cls(self.driver)
        return page

    def go_to_sales_history(self):
        from pages.sales_history_page import SalesHistoryPage

        logger.info("Navigating to Sales History")
        self.open()
        self.click(NavDrawerLocators.SALES_HISTORY)
        return SalesHistoryPage(self.driver)

    def go_to_fulfillment(self):
        from pages.fulfillment_page import FulfillmentPage

        logger.info("Navigating to Fulfillment")
        self.open()
        self.click(NavDrawerLocators.FULFILLMENT)
        return FulfillmentPage(self.driver)

    def go_to_dashboard(self):
        from pages.dashboard_page import DashboardPage

        self.open()
        self.click(NavDrawerLocators.HOME)
        dash = DashboardPage(self.driver)
        self.find(DashboardLocators.TITLE, timeout=20)
        return dash
