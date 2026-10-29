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

    def add_product_all_uom_tiers(self, product: dict, piece_qty: int = 1) -> list[str]:
        """Add every configured tier of a UOM product (Piece/Pack/Case/
        Pallet, custom labels on tiers 2-4) as 4 SEPARATE cart lines.

        The first tier (Piece) goes through the normal search + Add To Cart
        flow, with `piece_qty` set via the stepper shown before Add To Cart
        is tapped. The app has no Unit selector before that point - all 4
        tiers share one SKU and one search result - so the other 3 tiers
        are each added via the cart line's own "Add another unit" menu,
        which lists only the tiers not yet in the cart by their configured
        label (confirmed live 2026-10-29). Those 3 always land at qty=1:
        once a line exists, "Order Qty *" is a read-only View, not an
        EditText, and nothing in the UI opens a qty editor for it - there is
        no app-side way to make it anything else right now. Fails fast if a
        tier never produces its own cart line (matched by SKU+UPC, since
        UPC is the only thing that tells same-SKU tier lines apart).

        Returns the 4 UPCs in Piece/Pack/Case/Pallet order.
        """
        sku = product["sku"]
        self.add_product_by_sku(sku, qty=piece_qty)
        upcs = [product["piece_upc"]]
        for label, upc in (
            (product["pack_desc"], product["pack_upc"]),
            (product["case_desc"], product["case_upc"]),
            (product["pallet_desc"], product["pallet_upc"]),
        ):
            self.click(L.ADD_ANOTHER_UNIT)
            time.sleep(1)
            self.click(L.unit_option(label))
            time.sleep(2)
            assert self.is_in_cart(sku, upc=upc), (
                f"Tier '{label}' did not produce its own cart line (SKU {sku}, UPC {upc})")
            upcs.append(upc)
        return upcs

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

    def is_in_cart(self, sku: str, upc: str | None = None, timeout: int = 15) -> bool:
        return self.is_displayed(L.cart_line(sku, upc), timeout)

    def set_cart_quantity(self, sku: str, qty: int, upc: str | None = None):
        """Set the Order Qty on one cart line. Finds the qty EditText as a
        CHILD of the exact line element (via UIA descriptionContains, which
        matches only that element's own content-desc - unambiguous even
        when several same-SKU UOM-tier lines are in the cart), rather than
        a standalone global XPath: that pattern matched the wrong row (or
        nothing clickable) once multiple same-SKU lines existed - confirmed
        live 2026-10-29, the global `//View[contains(...)]//EditText[2]`
        form was never exercised by a passing single-line test before."""
        from selenium.common.exceptions import StaleElementReferenceException

        last_exc = None
        for attempt in range(3):
            try:
                line_el = self.swipe_to(L.cart_line(sku, upc))
                qty_field = line_el.find_element(AppiumBy.XPATH, './/android.widget.EditText[2]')
                qty_field.click()
                qty_field.clear()
                qty_field.send_keys(str(qty))
                self.hide_keyboard()
                return self
            except StaleElementReferenceException as e:
                last_exc = e
                logger.debug(f"Stale cart line on attempt {attempt + 1}/3 for {sku}/{upc}, retrying")
                time.sleep(0.5)
        raise last_exc

    def get_cart_line(self, sku: str, upc: str | None = None) -> dict:
        """Parse a cart line's content-desc into {name, category, sku, upc,
        available, sale_price, sub_total}. Pass `upc` to target one tier of
        a UOM product - all of its tiers share the same SKU."""
        el = self.swipe_to_either(L.cart_line(sku, upc))
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
