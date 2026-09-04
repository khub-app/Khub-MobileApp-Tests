import time

from locators.fulfillment_locators import FulfillmentLocators as L
from pages.base_page import BasePage
from utilities.logger import get_logger

logger = get_logger(__name__)


class PickingPage(BasePage):
    """The order's picking detail page and the active picking list.

    Flow: detail page ("Order Info" + "Start Picking") -> tap Start Picking ->
    status dialog OK -> picking list ("Skip Scan Pick All" / "Complete
    Picking") -> Skip Scan Pick All -> "still products to pick, continue?" Yes
    -> "confirm picking your order?" Pick -> picking complete, "Start Packing"
    becomes available.
    """

    def is_detail_shown(self, timeout: int = 25) -> bool:
        return self.is_displayed(L.ORDER_INFO, timeout) or \
            self.is_displayed(L.START_PICKING, timeout)

    def start_picking(self):
        logger.info("Tapping Start Picking")
        self.swipe_to(L.START_PICKING)
        self.click(L.START_PICKING)
        time.sleep(2)
        # "Sale order status changed - products can now be picked" info dialog
        try:
            self.tap_ok(labels=("OK", "Ok", "Done"), timeout=15)
        except AssertionError:
            logger.info("No status dialog after Start Picking")
        time.sleep(1)
        return self

    def skip_scan_pick_all(self):
        logger.info("Skip Scan Pick All -> Yes -> Pick")
        self.swipe_to(L.SKIP_SCAN_PICK_ALL)
        self.click(L.SKIP_SCAN_PICK_ALL)
        # dialog 1: "There are still some products to be picked. Continue?"
        self.tap_ok(labels=("Yes", "Continue"), timeout=20)
        # dialog 2: "Do you want to confirm picking your order?"
        self.tap_ok(labels=("Pick", "Confirm", "Yes"), timeout=20)
        time.sleep(3)
        # optional "picked successfully" info dialog
        try:
            self.tap_ok(labels=("OK", "Ok", "Done"), timeout=8)
        except AssertionError:
            pass
        time.sleep(2)
        return self

    def is_all_picked(self, timeout: int = 40) -> bool:
        """Picking succeeded once the flow offers the packing stage."""
        return self.is_displayed(L.START_PACKING, timeout)

    def start_packing(self):
        from pages.packing_page import PackingPage

        logger.info("Tapping Start Packing")
        self.swipe_to(L.START_PACKING)
        self.click(L.START_PACKING)
        time.sleep(2)
        page = PackingPage(self.driver)
        return page
