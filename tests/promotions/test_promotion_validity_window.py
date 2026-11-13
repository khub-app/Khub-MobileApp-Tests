"""A promotion's time window must be honored: a promotion that hasn't
started yet, or has already ended, must show NO discount - a correctness
guarantee no other promotion test here exercises (every other scenario's
promotion starts "now" with no end date).

Two Basic promotions, each on its own product, both configured with
REWARD_PERCENT=20% off and a wide qty range (1-10, so this test is purely
about the TIME window, not the qty range already covered elsewhere):
  - not_started: start_datetime 2 days in the future.
  - expired: start_datetime 2 days ago, end_datetime 1 day ago.

Confirmed live 2026-11-10: both show a completely plain line - no banner,
no discounted-price pair, and (unlike a qty-range-ineligible Basic promo,
which still shows its "Range:" indicator) no "Range:" line either. A
temporally-ineligible promotion leaves no trace on the line at all.

Mobile never creates the promotion/products itself - see
test_promotion_multi_tier.py's module docstring and
khub-web-tests/docs/mobile_promotion_api_handoff.md for the full data
contract.
"""
import allure
import pytest
import yaml

from tests.mobile_base_setup import MobileBaseSetup
from utilities import promotion_data
from utilities.api_client import ApiClient
from utilities.currency import money, parse_currency
from utilities.logger import get_logger
from utilities.promotion_asserts import assert_promo_state

logger = get_logger(__name__)

with open("data/test_data.yaml", "r", encoding="utf-8") as f:
    TEST_DATA = yaml.safe_load(f)

CFG = TEST_DATA["promotion_sale"]
QTY = 3


@allure.suite("Marketing Promotions")
@allure.feature("Promotions")
@allure.story("A not-yet-started or already-expired promotion applies NO discount")
@pytest.mark.promotion
@pytest.mark.e2e
class TestPromotionValidityWindow(MobileBaseSetup):

    # ---- shared context ----
    scenario = None
    customer_name = None
    not_started_sku = None
    not_started_upc = None
    expired_sku = None
    expired_upc = None

    grand_total = None
    order_no = None

    sales_history = None
    cso = None
    cart_summary = None
    payment = None

    # ---------------------------------------------------------------- #
    @allure.title("Load the validity_window scenario and resolve both products' SKUs")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_01_load_scenario_data(self):
        with allure.step("Read testdata/mobile_promotion_scenarios_<env>.json ('validity_window')"):
            scenario = promotion_data.get_scenario("validity_window", env=CFG["env"])
            TestPromotionValidityWindow.scenario = scenario
            TestPromotionValidityWindow.customer_name = scenario["customer"]
            TestPromotionValidityWindow.not_started_upc = scenario["not_started"]["product"]["piece_upc"]
            TestPromotionValidityWindow.expired_upc = scenario["expired"]["product"]["piece_upc"]
            logger.info(f"not_started promo starts {scenario['not_started']['start_datetime']} (future); "
                        f"expired promo ran {scenario['expired']['start_datetime']} -> "
                        f"{scenario['expired']['end_datetime']} (past)")
        with allure.step("Resolve both products' SKUs by UPC"):
            client = ApiClient()
            ns = client.get_product_by_upc(self.not_started_upc)
            ex = client.get_product_by_upc(self.expired_upc)
            assert ns and ex, f"Product lookup failed: not_started={ns} expired={ex}"
            TestPromotionValidityWindow.not_started_sku = ns["sku"]
            TestPromotionValidityWindow.expired_sku = ex["sku"]

    # ---------------- Part 1: open Sales History -> Create Sale Order --- #
    @allure.title("Open Sales History and start a new sale order")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_02_open_create_sale_order(self):
        with allure.step("Dashboard -> hamburger -> Sales History -> + FAB"):
            assert self.dashboard.is_loaded(), "Dashboard not shown"
            sh = self.dashboard.go_to_sales_history()
            assert sh.is_loaded(), "Sales History did not open"
            TestPromotionValidityWindow.sales_history = sh
            TestPromotionValidityWindow.cso = sh.tap_create_sale_order()
            assert self.cso.is_loaded(), "Create Sale Order page did not open"

    # ---------------- Part 2: customer + order info -------------------- #
    @allure.title("Add customer and order information")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_03_customer_and_order_info(self):
        name = self.customer_name
        with allure.step(f"Select customer '{name}' and verify it is applied"):
            self.cso.select_customer(name)
            assert self.cso.is_customer_selected(name), f"Customer {name} not selected"
        with allure.step("Order Type = Online, add unique internal + invoice notes, Next"):
            self.cso.set_order_type(CFG["order_type"])
            self.cso.set_internal_note(f"{CFG['internal_note_prefix']}-validity-window")
            self.cso.set_invoice_note(f"{CFG['invoice_note_prefix']}-validity-window")
            self.cso.tap_next()
            assert self.cso.is_product_step_loaded(), "Did not reach the product-selection step"

    # ---------------- Part 3: both products are plain, full price ------- #
    @allure.title("Both the not-started and the expired promo's products are plain, full price")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_04_add_both_products_no_discount(self):
        for label, sku, upc in (
            ("not_started", self.not_started_sku, self.not_started_upc),
            ("expired", self.expired_sku, self.expired_upc),
        ):
            with allure.step(f"Add '{label}' product at qty={QTY} - must be plain"):
                self.cso.add_product_by_sku(sku, qty=QTY, upc=upc)
                line = self.cso.get_cart_line(sku, upc=upc)
                assert_promo_state(line, False,
                    f"'{label}' promotion should be outside its time window - ")
                assert "promo_name" not in line, (
                    f"'{label}' line shows a promo tag at all (expected none): {line}")
                expected_full = money(line["sale_price"] * QTY)
                assert money(line["sub_total"]) == expected_full, (
                    f"'{label}' Sub Total {line.get('sub_total')} != {expected_full}")
                assert money(line["line_total"]) == expected_full, (
                    f"'{label}' Total {line.get('line_total')} != {expected_full} - "
                    f"should be full, undiscounted price")
        with allure.step("Next -> Cart Summary"):
            TestPromotionValidityWindow.cart_summary = self.cso.tap_next_to_summary()

    # ---------------- Part 4: validate the cart summary ------------------ #
    @allure.title("Validate Cart Summary: no Promo Savings row at all, full-price Grand Total")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_05_validate_cart_summary(self):
        cs = self.cart_summary
        with allure.step("Total quantity, full-price Sub Total, NO Promo Savings, Grand Total"):
            cs.scroll_to_summary()
            assert cs.get_total_quantity() == QTY * 2, "Total Quantity != 2 products x qty each"
            promo_savings = cs.get_promo_savings()
            assert money(promo_savings) == money(0), (
                f"Promo Savings is {promo_savings}, expected the row to be entirely absent/zero - "
                f"neither promotion is inside its time window")
            assert money(cs.get_additional_discount()) == money(0), "Additional Discount is not $0.00"
            tax = money(cs.get_tax())
            TestPromotionValidityWindow.grand_total = money(cs.get_grand_total())
            expected_subtotal = money(cs.get_sub_total())
            assert self.grand_total == money(expected_subtotal + tax), (
                f"Grand Total {self.grand_total} != Sub Total {expected_subtotal} + tax {tax}")
        with allure.step("Proceed to Checkout"):
            TestPromotionValidityWindow.payment = cs.proceed_to_checkout()

    # ---------------- Part 5: complete the sale with cash ----------------- #
    @allure.title("Pay in full with Cash and complete the sale")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_06_complete_cash_sale(self):
        pay = self.payment
        with allure.step("Invoice Total == Grand Total; correct customer"):
            assert pay.is_loaded(), "Payment page not shown"
            assert money(pay.get_invoice_total()) == self.grand_total, "Invoice Total != captured Grand Total"
            assert self.customer_name in pay.get_customer(), "Payment page shows the wrong customer"
        with allure.step("Select Cash; amount is the full invoice total"):
            pay.select_cash()
            assert money(pay.get_amount()) == self.grand_total, "Cash amount != Grand Total"
        with allure.step("Complete Sale -> success dialog -> OK"):
            pay.complete_sale()
            msg = pay.wait_success_dialog()
            assert "saved successfully" in msg, f"Unexpected success message: {msg!r}"
            TestPromotionValidityWindow.sales_history = pay.tap_ok_return_to_sales_history()

    # ---------------- Part 6: validate in Sales History ------------------- #
    @allure.title("Validate the new order in Sales History shows full, undiscounted totals")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_07_validate_sales_history(self):
        sh = self.sales_history
        with allure.step("Locate the newest card for this customer, capture Order Number"):
            order_no = sh.capture_latest_order_no(self.customer_name)
            assert order_no.startswith("SO-"), f"Order number {order_no!r} not in SO- format"
            TestPromotionValidityWindow.order_no = order_no
        with allure.step("Card: customer / Online / Paid / Sale Total == full-price Grand Total"):
            card = sh.get_order_card(order_no)
            assert card.get("Business Name", "").strip() == self.customer_name, "Business Name mismatch"
            assert card.get("Order Type") == "Online", f"Order Type = {card.get('Order Type')!r}"
            assert card.get("Invoice Status") == "Paid", f"Invoice Status = {card.get('Invoice Status')!r}"
            assert money(parse_currency(card.get("Sale Total", "0"))) == self.grand_total, (
                f"Sale Total {card.get('Sale Total')} != Grand Total {self.grand_total}")
