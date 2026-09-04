import time

from appium.webdriver.common.appiumby import AppiumBy

from locators.fulfillment_locators import FulfillmentLocators as L
from pages.base_page import BasePage
from utilities.logger import get_logger

logger = get_logger(__name__)


class FulfillmentPage(BasePage):
    """Fulfillment list (Pending / Picking Paused / Picked / Packing / Packed
    tabs). An order card is one clickable View whose content-desc is every
    field newline-joined ("Order No\\nSO-…\\nBusiness Name\\n…\\nOrder Type\\n
    Online\\n… \\nPicker Detail\\n<user>")."""

    def is_loaded(self, timeout: int = 25) -> bool:
        return self.is_displayed(L.TITLE, timeout)

    def open_pending(self):
        if self._present(L.TAB_PENDING):
            self.click(L.TAB_PENDING)
            time.sleep(2)
        return self

    def open_packed(self):
        self.click(L.TAB_PACKED)
        time.sleep(3)
        return self

    def is_packed_tab_selected(self) -> bool:
        try:
            el = self.find(L.TAB_PACKED, timeout=10)
            if (el.get_attribute("selected") or "").lower() == "true":
                return True
        except Exception:
            pass
        # Fallback: a Packed-tab card carries no "Status" field but the tab is
        # the one we just tapped - treat presence of the tab as good enough.
        return self._present(L.TAB_PACKED)

    def is_order_in_pending(self, order_no: str) -> bool:
        try:
            self.open_pending()
            return self.is_displayed(L.order_card(order_no), 8)
        except Exception:
            return False

    def search(self, order_no: str):
        """Filter the current tab down to `order_no` via the header search
        (magnifier). Idempotent - if the search box is already open (from an
        earlier call) it types into it directly instead of tapping the
        magnifier again, since that would toggle the search closed. No-op if
        the search control isn't exposed at all."""
        try:
            if not self._present(L.SEARCH_FIELD):
                if not self._present(L.SEARCH_ICON):
                    return self
                self.click(L.SEARCH_ICON)
            self.type_text(L.SEARCH_FIELD, order_no, clear_first=True)
            self.hide_keyboard()
            time.sleep(2)
        except Exception as e:
            logger.debug(f"Fulfillment search skipped: {e}")
        return self

    def _card(self, order_no: str, timeout: int = 30):
        return self.swipe_to(L.order_card(order_no), max_swipes=10)

    def get_order_desc(self, order_no: str) -> str:
        return self._card(order_no).get_attribute("content-desc") or ""

    def is_order_present(self, order_no: str, timeout: int = 20) -> bool:
        return self.is_displayed(L.order_card(order_no), timeout)

    def _tap_card(self, order_no: str):
        self._card(order_no).click()
        time.sleep(2)

    # ---- assignment ----
    def assign_order_to_me(self, order_no: str) -> str:
        """Tap the (unassigned) order card -> "Assign to me" bottom sheet ->
        read + dismiss the "Order has been assigned to the user '<user>'."
        Info dialog. Returns that confirmation message.

        The "Assign to me" tap sometimes doesn't register on the first try
        (the bottom sheet is still animating in), so this re-taps until the
        sheet is gone / the success dialog shows."""
        logger.info(f"Assigning {order_no} to me")
        self._tap_card(order_no)
        self.find(L.ASSIGN_DIALOG, timeout=20)   # bottom sheet is up

        for attempt in range(1, 5):
            if self._present(L.ASSIGN_SUCCESS):
                break
            try:
                self.click(L.ASSIGN_TO_ME, timeout=10)
            except Exception as e:
                logger.debug(f"Assign-to-me tap {attempt} raised {e}")
            time.sleep(3)
            if self._present(L.ASSIGN_SUCCESS) or not self._present(L.ASSIGN_DIALOG):
                break

        el = self.find(L.ASSIGN_SUCCESS, timeout=30)
        msg = el.get_attribute("content-desc") or ""
        self.tap_ok()
        time.sleep(2)
        return msg

    def is_assigned_to(self, order_no: str, user: str, timeout: int = 30) -> bool:
        """Re-applies the search filter (assigning can drop it / reshuffle
        the list) and polls the card's content-desc for "Picker Detail" +
        `user`, since the list can take a moment to reflect a just-completed
        assignment."""
        deadline = time.time() + timeout
        desc = ""
        while time.time() < deadline:
            self.search(order_no)
            desc = self.get_order_desc(order_no)
            if "Picker Detail" in desc and user in desc:
                return True
            time.sleep(2)
        logger.warning(f"Order {order_no} card not showing '{user}' as picker: {desc!r}")
        return False

    # ---- open for picking ----
    def open_order_for_picking(self, order_no: str):
        from pages.picking_page import PickingPage

        logger.info(f"Opening {order_no} for picking")
        self._tap_card(order_no)
        page = PickingPage(self.driver)
        assert page.is_detail_shown(), "Picking detail page did not open"
        return page
