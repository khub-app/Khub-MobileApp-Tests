import re
import time

from appium.webdriver.common.appiumby import AppiumBy

from locators.create_sale_order_locators import CreateSaleOrderLocators as L
from pages.base_page import BasePage
from utilities.currency import parse_currency
from utilities.logger import get_logger

logger = get_logger(__name__)


class CreateSaleOrderPage(BasePage):
    """Covers both wizard steps: step 1 (customer + order info) and step 2
    (product selection). `tap_next()` on step 1 moves to step 2; `tap_next()`
    on step 2 moves to the Cart Summary page."""

    def is_loaded(self, timeout: int = 20) -> bool:
        return self.is_displayed(L.TITLE, timeout)

    # ---------- step 1 ----------
    def select_customer(self, name: str):
        logger.info(f"Selecting customer: {name}")
        self.type_text(L.CUSTOMER_SEARCH, name)
        # Debounced, network-backed search on a slow emulator - wait for the
        # matching result row to render, then tap it.
        self.find(L.customer_result(name), timeout=60)
        self.click(L.customer_result(name))
        self.hide_keyboard()
        self.find(L.SELECTED_CUSTOMER_MARKER, timeout=20)
        return self

    def get_selected_customer_fields(self) -> list[str]:
        """All content-descs of the selected-customer summary card (name,
        Phone:, <phone>, Email:, <email>, ..., Customer No:, <no>, ...)."""
        from appium.webdriver.common.appiumby import AppiumBy as _By

        return [e.get_attribute("content-desc")
                for e in self.driver.find_elements(_By.XPATH, '//*[@content-desc]')]

    def is_customer_selected(self, name: str, timeout: int = 15) -> bool:
        return self.is_displayed(L.SELECTED_CUSTOMER_MARKER, timeout) and \
            self.is_displayed(L.customer_result(name), 5)

    def set_order_type(self, value: str = "Online"):
        logger.info(f"Setting Order Type = {value}")
        self.click(L.ORDER_TYPE_DROPDOWN)
        time.sleep(1)
        self.click(L.dropdown_option(value))
        time.sleep(1)
        assert self.is_displayed(L.order_type_value(value), 10), \
            f"Order Type did not switch to {value}"
        return self

    def set_internal_note(self, text: str):
        logger.info("Entering internal note")
        self.swipe_to(L.NOTES_INTERNAL)
        self.type_text(L.NOTES_INTERNAL, text)
        self.hide_keyboard()
        return self

    def set_invoice_note(self, text: str):
        logger.info("Entering print-on-invoice note")
        self.swipe_to(L.NOTES_INVOICE)
        self.type_text(L.NOTES_INVOICE, text)
        self.hide_keyboard()
        return self

    def tap_next(self):
        logger.info("Tapping Next")
        self.swipe_to(L.NEXT_BUTTON)
        self.click(L.NEXT_BUTTON)
        return self

    # ---------- step 2: products ----------
    def is_product_step_loaded(self, timeout: int = 20) -> bool:
        return self.is_displayed(L.PRODUCT_STEP_MARKER, timeout)

    def add_product_by_sku(self, sku: str, qty: int = 1, price: float | None = None,
                           search_timeout: int = 240):
        """Search a product by SKU, select the exact match, set its order
        quantity, and tap Add To Cart. Leaves the search box empty.

        The search is backend-indexed and a just-created product can take a
        while to become searchable (preprod's index lag varies from seconds
        to a few minutes), so this re-types the query and polls up to
        `search_timeout`s rather than a single 60s wait."""
        logger.info(f"Adding product SKU={sku} qty={qty}")
        result = self._search_product_result(sku, search_timeout)
        assert sku in (result.get_attribute("content-desc") or ""), \
            f"Search result does not match SKU {sku}"
        result.click()
        self.hide_keyboard()
        time.sleep(1)
        if qty != 1:
            try:
                self.type_text(L.SELECT_QTY_FIELD, str(qty), clear_first=True)
                self.hide_keyboard()
            except Exception as e:
                logger.warning(f"Could not set qty on selection popup: {e}")
        self.click(L.ADD_TO_CART_BUTTON)
        time.sleep(1)
        assert self.is_in_cart(sku), f"Product {sku} did not appear in the cart"
        return self

    def _search_product_result(self, sku: str, timeout: int):
        deadline = time.time() + timeout
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            self.type_text(L.PRODUCT_SEARCH, sku, clear_first=True)
            self.hide_keyboard()
            for _ in range(6):                       # ~18s per typed query
                time.sleep(3)
                hits = self.find_all(L.product_result(sku))
                if hits:
                    if attempt > 1:
                        logger.info(f"SKU {sku} became searchable on attempt {attempt}")
                    return hits[0]
            logger.info(f"SKU {sku} not in search results yet (attempt {attempt}) - retrying")
        raise AssertionError(
            f"Product SKU {sku} was not searchable within {timeout}s - the backend "
            f"catalog index is likely lagging; try again once it catches up.")

    def is_in_cart(self, sku: str, timeout: int = 15) -> bool:
        return self.is_displayed(L.cart_line(sku), timeout)

    def set_cart_quantity(self, sku: str, qty: int):
        self.swipe_to(L.cart_line(sku))
        self.type_text(L.cart_line_qty_field(sku), str(qty), clear_first=True)
        self.hide_keyboard()
        return self

    def get_cart_line(self, sku: str) -> dict:
        """Parse a cart line's content-desc into {name, category, sku, upc,
        available, sale_price, sub_total}."""
        el = self.swipe_to(L.cart_line(sku))
        raw = el.get_attribute("content-desc") or ""
        parts = [p.strip() for p in raw.split("\n") if p.strip()]
        info = {"raw": raw}
        if parts:
            info["name"] = parts[0]
        for i, p in enumerate(parts):
            if "/" in p and p.split("/")[0].strip() == sku:
                info["sku"], info["upc"] = [x.strip() for x in p.split("/", 1)]
            if p.startswith("Sale Price:"):
                info["sale_price"] = parse_currency(p)
            if p.startswith("Qty:"):
                info["available"] = int(re.sub(r"\D", "", p) or 0)
            if p == "Sub Total" and i + 1 < len(parts):
                info["sub_total"] = parse_currency(parts[i + 1])
            if p.startswith("Total:"):
                info["line_total"] = parse_currency(p)
        return info

    def cart_skus(self) -> list[str]:
        els = self.driver.find_elements(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().descriptionContains("Sub Total")')
        return [e.get_attribute("content-desc") for e in els]

    def tap_next_to_summary(self):
        from pages.cart_summary_page import CartSummaryPage

        logger.info("Tapping Next -> Cart Summary")
        self.swipe_to(L.NEXT_BUTTON)
        self.click(L.NEXT_BUTTON)
        page = CartSummaryPage(self.driver)
        assert page.is_loaded(), "Cart Summary page did not open"
        return page
