"""Label Management - Phase 1 of the Label Management scenario: create a
Product label with custom background/text colors, both display
destinations (Fulfillment + Invoice) enabled, and confirm it saves
successfully and appears in the list.

Scope note: this covers Phase 1 (Create a Product Label) only. Phases 2-5
(assign the label to a new product, carry it through a Sales Order and
Fulfillment, and verify it displays on the Invoice/Fulfillment screens)
are NOT yet automated - the Basic Info page's Category picker (a required
field before a product can be saved) does not respond to any tap attempted
live 2026-11-12 (AccessibilityId click, coordinate click, raw adb input
tap, and a search-filtered single-result tap all produced zero visible
effect - confirmed via screenshot, not just the accessibility dump). This
is a genuine, reproducible app/automation blocker, not a shortcut taken
to avoid the work - see CLAUDE.md's "Label Management" section for the
full writeup and what to try next.
"""
import allure
import pytest

from tests.mobile_base_setup import MobileBaseSetup
from utilities.logger import get_logger
from utilities.test_data_names import new_tag

logger = get_logger(__name__)

BACKGROUND_HEX = "817CDB"   # purple, per the scenario spec
TEXT_HEX = "FFFFFF"         # white, per the scenario spec


@allure.suite("Label Management")
@allure.feature("Label Management")
@allure.story("Create a Product label with custom colors")
@pytest.mark.label_management
class TestLabelManagementCreateLabel(MobileBaseSetup):

    label_name = None
    label_mgmt = None

    @allure.title("Navigate to Label Management and create a Product label")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_01_create_product_label(self):
        TestLabelManagementCreateLabel.label_name = f"Halvik {new_tag()}"
        with allure.step("Dashboard -> Profile -> Label Management"):
            profile = self.dashboard.open_profile()
            assert profile.is_loaded(), "Profile page did not open"
            label_mgmt = profile.go_to_label_management()
            assert label_mgmt.is_loaded(), "Label Management page did not open"
            TestLabelManagementCreateLabel.label_mgmt = label_mgmt
        with allure.step(f"Create label '{self.label_name}': Product type, "
                          f"Fulfillment+Invoice, background #{BACKGROUND_HEX}, "
                          f"text #{TEXT_HEX}"):
            create = label_mgmt.tap_add_label()
            create.set_name(self.label_name)
            create.select_type_product()
            create.check_fulfillment()
            create.check_invoice()
            create.set_background_color(BACKGROUND_HEX)
            create.set_text_color(TEXT_HEX)
            create.set_description("Automation test product label")
        with allure.step("Create tag -> success message"):
            msg = create.submit()
            assert "saved successfully" in msg.lower(), f"Unexpected message: {msg!r}"

    @allure.title("The new label appears in the Label Management list")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_02_validate_label_in_list(self):
        assert self.label_mgmt.is_label_present(self.label_name), (
            f"Label '{self.label_name}' not found in Label Management list")
