import time

from locators.label_management_locators import CreateLabelLocators as CL
from locators.label_management_locators import LabelManagementLocators as L
from pages.base_page import BasePage
from utilities.logger import get_logger

logger = get_logger(__name__)


class LabelManagementPage(BasePage):
    """Profile > Label Management - a plain list of label cards plus a
    "+" FAB that opens the Create Label modal."""

    def is_loaded(self, timeout: int = 20) -> bool:
        return self.is_displayed(L.TITLE, timeout)

    def tap_add_label(self):
        logger.info("Tapping the + button to create a label")
        self.click(L.ADD_BUTTON)
        page = CreateLabelPage(self.driver)
        assert page.is_loaded(), "Create Label modal did not open"
        return page

    def is_label_present(self, name: str, timeout: int = 15) -> bool:
        return self.is_displayed(L.label_card(name), timeout)


class CreateLabelPage(BasePage):
    """The "Create Label" modal. Only valid for CREATING a fresh label -
    relies on the Background/Text Color fields still showing their
    factory defaults (#FFFFFF / #000000) to identify them, and on
    Label Type still showing "Select" (unset). See locators module for
    details confirmed live 2026-11-12.

    Important: do NOT call self.hide_keyboard() anywhere on this modal -
    confirmed live that it falls back to an Android BACK press here, which
    dismisses the whole modal (not just the keyboard), discarding
    everything typed so far. Tapping the next field directly is enough;
    RN does not need an explicit keyboard-hide to keep typing elsewhere.
    """

    def is_loaded(self, timeout: int = 20) -> bool:
        return self.is_displayed(CL.TITLE, timeout)

    def set_name(self, name: str):
        logger.info(f"Setting label name: {name}")
        self.type_text(CL.LABEL_NAME_FIELD, name)
        return self

    def select_type_product(self):
        logger.info("Setting Label Type = Product")
        self.click(CL.LABEL_TYPE_DROPDOWN_UNSET)
        time.sleep(1)
        self.click(CL.LABEL_TYPE_PRODUCT_OPTION)
        time.sleep(1)
        return self

    def check_fulfillment(self):
        self.click(CL.FULFILLMENT_CHECKBOX)
        time.sleep(1)
        return self

    def check_invoice(self):
        self.click(CL.INVOICE_CHECKBOX)
        time.sleep(1)
        return self

    def _set_color(self, field_locator, hex6: str):
        """Open a color field's picker, type `hex6` (no leading '#') into
        its Hex input, and tap Apply."""
        self.click(field_locator)
        hex_field = None
        for _ in range(15):
            time.sleep(1)
            els = self.driver.find_elements(*CL.COLOR_HEX_INPUT)
            if els:
                hex_field = els[0]
                break
        assert hex_field is not None, "Color picker's Hex input did not appear"
        hex_field.click()
        hex_field.clear()
        hex_field.send_keys(hex6)
        time.sleep(1)
        self.click(CL.COLOR_APPLY_BUTTON)
        time.sleep(2)
        return self

    def set_background_color(self, hex6: str):
        logger.info(f"Setting Background Color = #{hex6}")
        return self._set_color(CL.BACKGROUND_COLOR_FIELD_DEFAULT, hex6)

    def set_text_color(self, hex6: str):
        logger.info(f"Setting Text Color = #{hex6}")
        return self._set_color(CL.TEXT_COLOR_FIELD_DEFAULT, hex6)

    def set_description(self, text: str):
        logger.info("Setting label description")
        self.type_text(CL.DESCRIPTION_FIELD, text)
        return self

    def submit(self) -> str:
        """Tap "Create tag" and return the success message's text. Leaves
        the driver on LabelManagementPage's list."""
        logger.info("Tapping Create tag")
        self.click(CL.CREATE_TAG_BUTTON)
        el = self.find(CL.SUCCESS_MESSAGE, timeout=20)
        msg = el.get_attribute("content-desc") or ""
        return msg
