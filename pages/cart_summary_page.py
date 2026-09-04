import re

from appium.webdriver.common.appiumby import AppiumBy

from locators.cart_summary_locators import CartSummaryLocators as L
from pages.base_page import BasePage
from utilities.currency import parse_currency
from utilities.logger import get_logger

logger = get_logger(__name__)

_NUMISH = re.compile(r"^\$?\s?[\d,]+(\.\d+)?$")


class CartSummaryPage(BasePage):
    """The summary section is a flat run of label / value Views, each with its
    own content-desc, and some labels have a non-value sibling in between
    (e.g. the Tax "+" icon). So values are read by scanning the ordered list
    of content-descs and taking the next numeric one after the label."""

    def is_loaded(self, timeout: int = 20) -> bool:
        return self.is_displayed(L.TITLE, timeout)

    def scroll_to_summary(self):
        self.swipe_to(L.GRAND_TOTAL_LABEL)
        return self

    def _descs(self) -> list[str]:
        return [e.get_attribute("content-desc")
                for e in self.driver.find_elements(AppiumBy.XPATH, '//*[@content-desc]')]

    def _value_after(self, label: str, last: bool = True) -> float:
        descs = [d for d in self._descs() if d]
        idxs = [i for i, d in enumerate(descs) if d == label]
        if not idxs:
            raise AssertionError(f"Cart Summary label {label!r} not found")
        start = idxs[-1] if last else idxs[0]
        for nxt in descs[start + 1:]:
            if _NUMISH.match(nxt.strip()):
                return parse_currency(nxt)
        raise AssertionError(f"No numeric value after {label!r} in {descs}")

    def get_total_products(self) -> int:
        self.scroll_to_summary()
        return int(self._value_after("Total Products"))

    def get_total_quantity(self) -> int:
        return int(self._value_after("Total Quantity"))

    def get_sub_total(self) -> float:
        return self._value_after("Sub Total")

    def get_additional_discount(self) -> float:
        return self._value_after("Additional Discount")

    def get_tax(self) -> float:
        return self._value_after("Tax")

    def get_grand_total(self) -> float:
        return self._value_after("Grand Total")

    def proceed_to_checkout(self):
        from pages.payment_page import PaymentPage

        logger.info("Proceeding to checkout")
        self.swipe_to(L.PROCEED_TO_CHECKOUT)
        self.click(L.PROCEED_TO_CHECKOUT)
        page = PaymentPage(self.driver)
        assert page.is_loaded(), "Payment page did not open"
        return page
