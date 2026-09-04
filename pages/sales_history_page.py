import re
import time

from appium.webdriver.common.appiumby import AppiumBy

from locators.sales_history_locators import SalesHistoryLocators
from pages.base_page import BasePage
from utilities.logger import get_logger

logger = get_logger(__name__)


_CARD_LABELS = {
    "Sr.No", "Order Number", "Date / Time", "Sold By", "Order Type",
    "Invoice Status", "Status", "Sale Total", "Business Name", "Actions", "Tags",
}


def _fields_from_desc(desc: str) -> dict:
    """The order card's content-desc is 'Label\\nValue\\nLabel\\nValue...'.
    Turn it into {label: value}. A label followed immediately by another
    label means that field's value is blank (e.g. an unset 'Sold By')."""
    parts = [p.strip() for p in (desc or "").split("\n") if p.strip()]
    out = {}
    for i, part in enumerate(parts):
        if part in _CARD_LABELS:
            nxt = parts[i + 1] if i + 1 < len(parts) else ""
            out[part] = "" if nxt in _CARD_LABELS else nxt
    return out


class SalesHistoryPage(BasePage):
    def is_loaded(self, timeout: int = 20) -> bool:
        return self.is_displayed(SalesHistoryLocators.TITLE, timeout)

    def _fab_sale_order_option(self):
        if self._present(SalesHistoryLocators.FAB_SALE_ORDER_OPTION_DESC):
            return SalesHistoryLocators.FAB_SALE_ORDER_OPTION_DESC
        if self._present(SalesHistoryLocators.FAB_SALE_ORDER_OPTION_TEXT):
            return SalesHistoryLocators.FAB_SALE_ORDER_OPTION_TEXT
        return None

    def tap_create_sale_order(self):
        """Tap the pink + FAB to reach Create Sale Order.

        The FAB sometimes expands into a speed-dial instead of navigating
        straight through - mini-FABs "Sale Order" / "Sale Return" appear
        and the main + morphs into an X (close). That X then sits where +
        was, so blindly re-tapping the same locator just toggles the dial
        shut again instead of opening anything. This taps the FAB, and on
        each attempt either finds itself already on Create Sale Order, taps
        the "Sale Order" option if the dial opened, or - if neither
        happened (a toggle-closed) - taps the FAB again."""
        from pages.create_sale_order_page import CreateSaleOrderPage

        logger.info("Tapping the + FAB to create a sale order")
        page = CreateSaleOrderPage(self.driver)
        for attempt in range(1, 4):
            self.click(SalesHistoryLocators.CREATE_FAB)
            time.sleep(1.5)
            if page.is_loaded(timeout=5):
                return page
            option = self._fab_sale_order_option()
            if option:
                logger.info("FAB expanded into a speed-dial - tapping 'Sale Order'")
                self.click(option)
                if page.is_loaded(timeout=15):
                    return page
            logger.info(f"Create Sale Order not open yet (attempt {attempt}), retrying FAB")

        assert page.is_loaded(timeout=15), "Create Sale Order page did not open"
        return page

    # ---- locating / reading a specific order ----
    def _card_desc(self, order_no: str, timeout: int = 30) -> str:
        el = self.swipe_to(SalesHistoryLocators.order_card(order_no))
        return el.get_attribute("content-desc") or ""

    def get_order_card(self, order_no: str, timeout: int = 30) -> dict:
        """Return the parsed field map for the order's list card."""
        return _fields_from_desc(self._card_desc(order_no, timeout))

    def is_order_present(self, order_no: str, timeout: int = 20) -> bool:
        return self.is_displayed(SalesHistoryLocators.order_card(order_no), timeout)

    def capture_latest_order_no(self, business_name: str, timeout: int = 30) -> str:
        """Scroll from the top and return the Order Number of the newest card
        whose Business Name matches `business_name` - never blindly the first
        row."""
        self._scroll_to_top()
        for _ in range(6):
            cards = self.driver.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().descriptionContains("Order Number")')
            for c in cards:
                fields = _fields_from_desc(c.get_attribute("content-desc"))
                if fields.get("Business Name", "").strip() == business_name.strip():
                    order_no = fields.get("Order Number", "").strip()
                    logger.info(f"Captured order number {order_no} for {business_name}")
                    return order_no
            self._swipe("up", 0.6)
        raise AssertionError(f"No Sales History card found for business '{business_name}'")

    def _scroll_to_top(self):
        for _ in range(6):
            self._swipe("down", 0.9)

    # ---- actions menu ----
    def open_order_details(self, order_no: str):
        from pages.order_details_page import OrderDetailsPage

        logger.info(f"Opening actions -> View Details for {order_no}")
        self.swipe_to(SalesHistoryLocators.order_card(order_no))
        self.click(SalesHistoryLocators.order_card_actions(order_no))
        time.sleep(1)
        self.tap_ok(labels=("View Details", "View Detail", "View Order", "Order Details",
                            "Details", "View"), timeout=15)
        return OrderDetailsPage(self.driver)
