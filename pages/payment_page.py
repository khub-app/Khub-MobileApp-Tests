import re
import time

from appium.webdriver.common.appiumby import AppiumBy

from locators.payment_locators import PaymentLocators as L
from pages.base_page import BasePage
from utilities.currency import parse_currency
from utilities.logger import get_logger

logger = get_logger(__name__)

_MONEY = re.compile(r"^\$?[\d,]+\.\d{2}$")


class PaymentPage(BasePage):
    def is_loaded(self, timeout: int = 25) -> bool:
        return self.is_displayed(L.HEADER, timeout)

    def _descs(self) -> list[str]:
        return [e.get_attribute("content-desc")
                for e in self.driver.find_elements(AppiumBy.XPATH, '//*[@content-desc]')]

    def _value_after(self, label: str) -> str:
        """The payment summary is a flat 2-column grid of label/value Views,
        so the value for `label` is the next content-desc after it that isn't
        itself another label."""
        descs = [d for d in self._descs() if d]
        for i, d in enumerate(descs):
            if d == label:
                for nxt in descs[i + 1:]:
                    if _MONEY.match(nxt) or (label == "Customer" and nxt):
                        return nxt
        raise AssertionError(f"No value found after {label!r} on the payment page")

    def get_invoice_total(self) -> float:
        return parse_currency(self._value_after("Invoice Total"))

    def get_customer(self) -> str:
        return self._value_after("Customer").strip()

    def select_cash(self):
        logger.info("Selecting Cash payment mode")
        self.click(L.CASH_MODE)
        time.sleep(1)
        return self

    def get_amount(self) -> float:
        el = self.find(L.AMOUNT_FIELD)
        val = el.get_attribute("text") or el.get_attribute("content-desc") or ""
        return parse_currency(val)

    def complete_sale(self):
        logger.info("Tapping Complete Sale")
        self.swipe_to(L.COMPLETE_SALE)
        self.click(L.COMPLETE_SALE)
        return self

    def wait_success_dialog(self, timeout: int = 40) -> str:
        el = self.find(L.SUCCESS_MESSAGE, timeout)
        return el.get_attribute("content-desc") or ""

    def tap_ok_return_to_sales_history(self):
        from pages.sales_history_page import SalesHistoryPage

        logger.info("Tapping OK on the success dialog")
        self.click(L.OK_BUTTON)
        page = SalesHistoryPage(self.driver)
        assert page.is_loaded(30), "Did not return to Sales History after completing the sale"
        return page
