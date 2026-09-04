import re

from locators.order_details_locators import OrderDetailsLocators as L
from pages.base_page import BasePage
from utilities.logger import get_logger

logger = get_logger(__name__)

_DESC_RE = re.compile(r'content-desc="([^"]*)"')


class OrderDetailsPage(BasePage):
    """View Details screen. Panels render as elements whose content-desc is
    every field newline-joined, so this page scrolls top-to-bottom and unions
    every content-desc / text it sees into one blob, then answers questions
    against that blob. Parsing page_source once per scroll is far faster than
    per-element Appium round-trips."""

    def is_shown(self, timeout: int = 20) -> bool:
        return self.is_displayed(L.contains("Order Number"), timeout) or \
            self.is_displayed(L.contains("Grand Total"), 5) or \
            self.is_displayed(L.contains("Order"), 5)

    def read_all_text(self, scrolls: int = 6) -> str:
        seen = []

        def harvest():
            for m in _DESC_RE.finditer(self.driver.page_source):
                v = m.group(1).replace("&#10;", "\n").replace("&amp;", "&")
                if v and v not in seen:
                    seen.append(v)

        for _ in range(scrolls):
            self._swipe("down", 0.9)
        harvest()
        for _ in range(scrolls):
            self._swipe("up", 0.75)
            harvest()
        blob = "\n".join(seen)
        logger.info(f"Order Details text blob ({len(blob)} chars)")
        return blob

    def contains_all(self, *needles: str) -> tuple[bool, list[str]]:
        blob = self.read_all_text()
        missing = [n for n in needles if n not in blob]
        return (not missing, missing)

    def go_back(self):
        from pages.sales_history_page import SalesHistoryPage

        logger.info("Navigating back from Order Details")
        try:
            self.click(L.BACK, timeout=10)
        except Exception:
            self.driver.back()
        return SalesHistoryPage(self.driver)
