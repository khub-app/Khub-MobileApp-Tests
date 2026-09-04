from locators.dashboard_locators import DashboardLocators
from pages.base_page import BasePage
from utilities.logger import get_logger

logger = get_logger(__name__)


class DashboardPage(BasePage):
    def is_loaded(self, timeout: int = 60) -> bool:
        return self.is_displayed(DashboardLocators.TITLE, timeout) and \
            self.is_displayed(DashboardLocators.TAB_HOME, 10)

    def open_tab(self, locator):
        self.click(locator)
        return self

    def open_sales(self):
        return self.open_tab(DashboardLocators.TAB_SALES)

    def open_fulfillment(self):
        return self.open_tab(DashboardLocators.TAB_FULFILLMENT)

    def open_customers(self):
        return self.open_tab(DashboardLocators.TAB_CUSTOMERS)

    def open_nav_drawer(self):
        from pages.nav_drawer_page import NavDrawerPage

        return NavDrawerPage(self.driver).open()

    def go_to_sales_history(self):
        from pages.nav_drawer_page import NavDrawerPage

        return NavDrawerPage(self.driver).go_to_sales_history()

    def go_to_fulfillment(self):
        from pages.nav_drawer_page import NavDrawerPage

        return NavDrawerPage(self.driver).go_to_fulfillment()
