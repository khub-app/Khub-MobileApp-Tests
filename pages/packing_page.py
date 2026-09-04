import time

from locators.fulfillment_locators import FulfillmentLocators as L
from pages.base_page import BasePage
from utilities.logger import get_logger

logger = get_logger(__name__)


class PackingPage(BasePage):
    """Packing Progress -> Skip Scan Pack All -> "products remain, continue?"
    Yes -> "confirm packing your order?" Pack -> "packed successfully" -> OK.
    Confirm-button labels mirror picking's ("Yes" then "Pack"); tap_ok tries
    several so a label change won't break it."""

    def is_shown(self, timeout: int = 25) -> bool:
        return self.is_displayed(L.SKIP_SCAN_PACK_ALL, timeout)

    def skip_scan_pack_all(self):
        logger.info("Skip Scan Pack All -> Yes -> Pack")
        self.swipe_to(L.SKIP_SCAN_PACK_ALL)
        self.click(L.SKIP_SCAN_PACK_ALL)
        # dialog 1: "There are still some products to be packed. Continue?"
        self.tap_ok(labels=("Yes", "Continue"), timeout=20)
        # dialog 2: "Do you want to confirm packing your order?"
        self.tap_ok(labels=("Pack", "Confirm", "Yes"), timeout=20)
        time.sleep(3)
        return self

    def wait_packed_success(self, timeout: int = 45) -> str:
        el = self.find(L.PACKED_SUCCESS, timeout)
        text = el.get_attribute("content-desc") or ""
        self.tap_ok()
        time.sleep(2)
        return text
