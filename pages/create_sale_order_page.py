import re
import time

from appium.webdriver.common.appiumby import AppiumBy

from locators.create_sale_order_locators import CreateSaleOrderLocators as L
from pages.base_page import BasePage
from utilities.currency import parse_currency
from utilities.logger import get_logger

logger = get_logger(__name__)

# A promoted cart line adds up to 3 extra pieces of info to the plain shape
# documented on `cart_line` below - confirmed live 2026-11-09 across all 4
# promotion-engine scenarios (Basic single-tier, Basic multi-tier, two
# overlapping Basics, and BXGY trigger+reward):
#   - a banner line, right after "Qty: <avail>": "<promo name> · <suffix>"
#     where <suffix> is "<percent>% off" on an actively-discounted line, or
#     "rewards line <n>" on a BXGY trigger line (which is itself never
#     discounted - skip_discounted_trigger).
#   - two extra bare "$<amount>" lines between "Sale Price:$<p>" and
#     "Order Qty *" (original price, then discounted price) - ONLY when the
#     line's current qty is actually within the promo's qualifying range;
#     at qty outside that range the banner and these two lines are both
#     absent entirely, even though the line is still promo-eligible.
#   - under "Order Qty *": "Range: <min>–<max>" for a Basic promo
#     (shown regardless of whether the current qty is in range), or
#     "Min: <trigger_qty>" / "Max: <max_reward_qty>" for a BXGY
#     trigger/reward line respectively.
_PROMO_BANNER_RE = re.compile(r"^(.+) · (.+)$")
_PERCENT_OFF_RE = re.compile(r"^(\d+(?:\.\d+)?)% off$")
_REWARDS_LINE_RE = re.compile(r"^rewards line (\d+)$")
_RANGE_RE = re.compile(r"^Range: (\d+)–(\d+)$")
_MIN_RE = re.compile(r"^Min: (\d+)$")
_MAX_RE = re.compile(r"^Max: (\d+)$")
_BARE_AMOUNT_RE = re.compile(r"^\$[\d,]+(?:\.\d+)?$")


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
                           search_timeout: int = 420, upc: str | None = None):
        """Search for a product, select the exact match, set its order
        quantity, and tap Add To Cart. Leaves the search box empty.

        Searches by `upc` when given, SKU otherwise. This shared preprod
        catalog has grown large enough that a short numeric SKU is often a
        substring of many unrelated products (another product's longer SKU,
        or its name) - confirmed live 2026-11-03: a product's exact SKU
        search could return zero matches even 7+ minutes after creation,
        crowded out by unrelated partial matches, while searching the same
        product's UPC (a random 10-digit number, no realistic collision
        risk) found it immediately. This was mistaken for backend index lag
        at first since the symptom (empty results, retried for the full
        `search_timeout`) looks identical - it isn't lag, so no amount of
        waiting fixes it; passing `upc` does.

        `search_timeout` default raised 240s -> 420s on 2026-11-05: with the
        catalog now at 18,000+ products, even a UPC search (collision-free,
        so not the crowding issue above) was confirmed - via a direct
        backend query of the same products the app's search indexes from -
        to sit genuinely unindexed in the app's live search for several
        minutes after creation, longer than the old 240s budget covered.
        This is real index lag, distinct from the crowding issue: the
        product exists and is correct (verified via
        `/tenant/api/v1/catalog/products/list3`) well before the app's own
        search surfaces it."""
        logger.info(f"Adding product SKU={sku} qty={qty}")
        result = self._search_product_result(upc or sku, sku, search_timeout)
        # Exact-line check, not a bare substring: this catalog's SKUs are
        # short sequential numbers, so a shorter SKU can be a literal prefix
        # of an unrelated, longer one (e.g. "2572" inside "25720") -
        # confirmed live 2026-11-03, where that silently matched and added
        # the wrong product. The SKU always sits on its own line.
        desc = result.get_attribute("content-desc") or ""
        assert f"\n{sku}\n" in desc, f"Search result does not match SKU {sku}: {desc!r}"
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
        self.add_product_by_sku(sku, qty=piece_qty, upc=product["piece_upc"])
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

    def _search_product_result(self, search_text: str, sku: str, timeout: int):
        """Types `search_text` (UPC when the caller has one, else the SKU)
        and polls for a result row matching `sku` exactly."""
        deadline = time.time() + timeout
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            self.type_text(L.PRODUCT_SEARCH, search_text, clear_first=True)
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
            f"Product SKU {sku} was not searchable (query {search_text!r}) within "
            f"{timeout}s - either backend index lag, or (if searching by SKU) the "
            f"exact match is being crowded out by unrelated partial matches in this "
            f"large shared catalog - retry with the product's UPC instead.")

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
        available, sale_price, sub_total, line_total}, plus - only when the
        line carries an active or eligible promotion (see the module-level
        comment above for the exact shape) - any of: promo_name,
        promo_percent, promo_rewards_line, promo_qty_min, promo_qty_max,
        promo_trigger_qty, promo_max_reward_qty, promo_original_price,
        promo_discounted_price, is_promo_active. Pass `upc` to target one
        tier of a UOM product - all of its tiers share the same SKU.

        `sub_total` is always qty x the undiscounted `sale_price` (the UI's
        own "Sub Total" label) - on a currently-discounted line this is
        NOT what the order is actually charged for that line; `line_total`
        (the UI's "Total:") is - confirmed live 2026-11-09 against the Cart
        Summary's own "Sub Total", which already nets out every line's
        promo discount."""
        el = self.swipe_to_either(L.cart_line(sku, upc))
        raw = el.get_attribute("content-desc") or ""
        parts = [p.strip() for p in raw.split("\n") if p.strip()]
        info = {"raw": raw}
        if parts:
            info["name"] = parts[0]
        sp_idx = oq_idx = None
        for i, p in enumerate(parts):
            if "/" in p and p.split("/")[0].strip() == sku:
                info["sku"], info["upc"] = [x.strip() for x in p.split("/", 1)]
            if p.startswith("Sale Price:"):
                info["sale_price"] = parse_currency(p)
                sp_idx = i
            if p.startswith("Qty:"):
                info["available"] = int(re.sub(r"\D", "", p) or 0)
            if p == "Order Qty *":
                oq_idx = i
            if p == "Sub Total" and i + 1 < len(parts):
                info["sub_total"] = parse_currency(parts[i + 1])
            if p.startswith("Total:"):
                info["line_total"] = parse_currency(p)

            banner = _PROMO_BANNER_RE.match(p)
            if banner:
                info["promo_name"] = banner.group(1)
                suffix = banner.group(2)
                pct = _PERCENT_OFF_RE.match(suffix)
                if pct:
                    info["promo_percent"] = float(pct.group(1))
                rewards = _REWARDS_LINE_RE.match(suffix)
                if rewards:
                    info["promo_rewards_line"] = int(rewards.group(1))
            rng = _RANGE_RE.match(p)
            if rng:
                info["promo_qty_min"], info["promo_qty_max"] = int(rng.group(1)), int(rng.group(2))
            mn = _MIN_RE.match(p)
            if mn:
                info["promo_trigger_qty"] = int(mn.group(1))
            mx = _MAX_RE.match(p)
            if mx:
                info["promo_max_reward_qty"] = int(mx.group(1))

        if sp_idx is not None and oq_idx is not None:
            price_lines = [parts[i] for i in range(sp_idx + 1, oq_idx) if _BARE_AMOUNT_RE.match(parts[i])]
            if len(price_lines) == 2:
                info["promo_original_price"] = parse_currency(price_lines[0])
                info["promo_discounted_price"] = parse_currency(price_lines[1])
        info["is_promo_active"] = "promo_discounted_price" in info
        return info

    def cart_skus(self) -> list[str]:
        els = self.driver.find_elements(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().descriptionContains("Sub Total")')
        return [e.get_attribute("content-desc") for e in els]

    def discard_order(self):
        """Exit the wizard from the product-selection step WITHOUT
        completing the order - e.g. to probe a promotion at several cart
        quantities, which this app has no way to edit on an existing line
        (see CLAUDE.md's UOM gotchas - Order Qty is a read-only View on a
        placed line). Confirmed live 2026-11-09: Android back once returns
        to step 1 (customer + order info intact), back again opens the
        "Confirmation" dialog; CONFIRM_DISCARD ("Go Back") discards cleanly
        and lands on Sales History, proven safe across several repeated
        fresh orders in the same session."""
        logger.info("Discarding the in-progress order")
        self.driver.back()
        time.sleep(1.5)
        self.driver.back()
        time.sleep(1.5)
        self.click(L.CONFIRM_DISCARD, timeout=10)
        from pages.sales_history_page import SalesHistoryPage

        page = SalesHistoryPage(self.driver)
        assert page.is_loaded(), "Sales History did not open after discarding the order"
        return page

    def tap_next_to_summary(self):
        from pages.cart_summary_page import CartSummaryPage

        logger.info("Tapping Next -> Cart Summary")
        self.swipe_to(L.NEXT_BUTTON)
        self.click(L.NEXT_BUTTON)
        page = CartSummaryPage(self.driver)
        assert page.is_loaded(), "Cart Summary page did not open"
        return page
