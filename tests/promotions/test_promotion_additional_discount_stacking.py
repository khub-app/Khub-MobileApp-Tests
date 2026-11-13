"""A manual "Additional Discount" entered on Cart Summary must stack
CLEANLY on top of an already-active promotion discount - neither
double-discounting the line nor getting clobbered by the promo engine.

Every other promotion test here only ever asserts Additional Discount is
exactly $0.00 (never actually used); `CartSummaryLocators.ADDITIONAL_DISCOUNT_FIELD`
was captured live long ago but never exercised. Confirmed live 2026-11-10,
reusing the already-proven `multi_tier` scenario's promoted product:
entering a manual discount leaves the promo-discounted Sub Total AND the
"Promo Savings" figure completely unchanged - it only reduces Grand Total
by exactly the entered amount. The two discount mechanisms are independent;
there is no interaction/bug to find here, but it was never actually proven
before this test.

Mobile never creates the promotion/product itself - see
test_promotion_multi_tier.py's module docstring and
khub-web-tests/docs/mobile_promotion_api_handoff.md for the full data
contract.
"""
from decimal import Decimal

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
ADDITIONAL_DISCOUNT = Decimal("30.00")


@allure.suite("Marketing Promotions")
@allure.feature("Promotions")
@allure.story("Manual Additional Discount stacks cleanly on top of an active promotion")
@pytest.mark.promotion
@pytest.mark.e2e
class TestPromotionAdditionalDiscountStacking(MobileBaseSetup):

    # ---- shared context ----
    scenario = None
    customer_name = None
    sku = None
    piece_upc = None
    promo_name = None
    reward_percent = None
    qty_min = None
    qty_max = None

    promo_discounted_subtotal = None   # Decimal - Cart Summary Sub Total BEFORE the manual discount
    promo_savings_before = None        # Decimal (positive)
    grand_total = None
    order_no = None

    sales_history = None
    cso = None
    cart_summary = None
    payment = None

    # ---------------------------------------------------------------- #
    @allure.title("Load the multi_tier scenario and resolve its product SKU")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_01_load_scenario_data(self):
        with allure.step("Read testdata/mobile_promotion_scenarios_<env>.json ('multi_tier')"):
            scenario = promotion_data.get_scenario("multi_tier", env=CFG["env"])
            TestPromotionAdditionalDiscountStacking.scenario = scenario
            params = scenario["params"]
            TestPromotionAdditionalDiscountStacking.customer_name = scenario["customer"]
            TestPromotionAdditionalDiscountStacking.piece_upc = scenario["product"]["piece_upc"]
            TestPromotionAdditionalDiscountStacking.promo_name = scenario["promotion"]["name"]
            TestPromotionAdditionalDiscountStacking.reward_percent = params["reward_percent"]
            TestPromotionAdditionalDiscountStacking.qty_min = params["min_qty"]
            TestPromotionAdditionalDiscountStacking.qty_max = params["max_reward_qty"]
        with allure.step("Resolve the product's SKU by UPC"):
            client = ApiClient()
            found = client.get_product_by_upc(self.piece_upc)
            assert found, f"Product with UPC {self.piece_upc} not found via backend search"
            TestPromotionAdditionalDiscountStacking.sku = found["sku"]

    # ---------------- Part 1: open Sales History -> Create Sale Order --- #
    @allure.title("Open Sales History and start a new sale order")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_02_open_create_sale_order(self):
        with allure.step("Dashboard -> hamburger -> Sales History -> + FAB"):
            assert self.dashboard.is_loaded(), "Dashboard not shown"
            sh = self.dashboard.go_to_sales_history()
            assert sh.is_loaded(), "Sales History did not open"
            TestPromotionAdditionalDiscountStacking.sales_history = sh
            TestPromotionAdditionalDiscountStacking.cso = sh.tap_create_sale_order()
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
            self.cso.set_internal_note(f"{CFG['internal_note_prefix']}-addl-discount")
            self.cso.set_invoice_note(f"{CFG['invoice_note_prefix']}-addl-discount")
            self.cso.tap_next()
            assert self.cso.is_product_step_loaded(), "Did not reach the product-selection step"

    # ---------------- Part 3: add the promoted product ------------------ #
    @allure.title("Add the promoted product within its qty range and validate the promo")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_04_add_promoted_product(self):
        with allure.step(f"Search + Add To Cart at qty={self.qty_min} (within the promo's range)"):
            self.cso.add_product_by_sku(self.sku, qty=self.qty_min, upc=self.piece_upc)
        with allure.step("Cart line is actively discounted"):
            line = self.cso.get_cart_line(self.sku, upc=self.piece_upc)
            assert_promo_state(line, True, "Expected an active discount - ")
            assert line["promo_name"] == self.promo_name
            assert line["promo_percent"] == self.reward_percent
        with allure.step("Next -> Cart Summary"):
            TestPromotionAdditionalDiscountStacking.cart_summary = self.cso.tap_next_to_summary()

    # ---------------- Part 4: capture pre-discount summary, then stack -- #
    @allure.title("Capture the promo-only summary, then apply a manual Additional Discount")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_05_apply_additional_discount_and_validate_stacking(self):
        cs = self.cart_summary
        with allure.step("Capture Sub Total / Promo Savings / Grand Total BEFORE any manual discount"):
            cs.scroll_to_summary()
            assert money(cs.get_additional_discount()) == money(0), "Additional Discount is not $0.00 to start"
            TestPromotionAdditionalDiscountStacking.promo_discounted_subtotal = money(cs.get_sub_total())
            TestPromotionAdditionalDiscountStacking.promo_savings_before = money(abs(cs.get_promo_savings()))
            grand_total_before = money(cs.get_grand_total())
            assert self.promo_savings_before > money(0), "Promo Savings should be non-zero before any manual discount"

        with allure.step(f"Enter Additional Discount = ${ADDITIONAL_DISCOUNT}"):
            cs.set_additional_discount(ADDITIONAL_DISCOUNT)

        with allure.step("Sub Total and Promo Savings are UNCHANGED; Grand Total drops by exactly the manual amount"):
            assert money(cs.get_sub_total()) == self.promo_discounted_subtotal, (
                f"Sub Total changed after manual discount: {cs.get_sub_total()} != "
                f"{self.promo_discounted_subtotal} - promo and manual discounts should be independent")
            assert money(cs.get_additional_discount()) == ADDITIONAL_DISCOUNT, (
                f"Additional Discount {cs.get_additional_discount()} != entered {ADDITIONAL_DISCOUNT}")
            assert money(abs(cs.get_promo_savings())) == self.promo_savings_before, (
                f"Promo Savings changed after a manual discount was added: {cs.get_promo_savings()} "
                f"!= {self.promo_savings_before} - the two discounts should not interact")
            TestPromotionAdditionalDiscountStacking.grand_total = money(cs.get_grand_total())
            assert self.grand_total == money(grand_total_before - ADDITIONAL_DISCOUNT), (
                f"Grand Total {self.grand_total} != pre-manual-discount total {grand_total_before} "
                f"- {ADDITIONAL_DISCOUNT} (no double-discount, no clobbering of the promo)")
            logger.info(f"Promo-only Grand Total was ${grand_total_before}, "
                        f"now ${self.grand_total} after stacking ${ADDITIONAL_DISCOUNT} manual discount")

        with allure.step("Proceed to Checkout"):
            TestPromotionAdditionalDiscountStacking.payment = cs.proceed_to_checkout()

    # ---------------- Part 5: complete the sale with cash ---------------- #
    @allure.title("Pay in full with Cash and complete the sale")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_06_complete_cash_sale(self):
        pay = self.payment
        with allure.step("Invoice Total == the stacked Grand Total; correct customer"):
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
            TestPromotionAdditionalDiscountStacking.sales_history = pay.tap_ok_return_to_sales_history()

    # ---------------- Part 6: validate in Sales History ------------------ #
    @allure.title("Validate the new order in Sales History reflects both discounts")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_07_validate_sales_history(self):
        sh = self.sales_history
        with allure.step("Locate the newest card for this customer, capture Order Number"):
            order_no = sh.capture_latest_order_no(self.customer_name)
            assert order_no.startswith("SO-"), f"Order number {order_no!r} not in SO- format"
            TestPromotionAdditionalDiscountStacking.order_no = order_no
        with allure.step("Card: customer / Online / Paid / Sale Total == final stacked Grand Total"):
            card = sh.get_order_card(order_no)
            assert card.get("Business Name", "").strip() == self.customer_name, "Business Name mismatch"
            assert card.get("Order Type") == "Online", f"Order Type = {card.get('Order Type')!r}"
            assert card.get("Invoice Status") == "Paid", f"Invoice Status = {card.get('Invoice Status')!r}"
            assert money(parse_currency(card.get("Sale Total", "0"))) == self.grand_total, (
                f"Sale Total {card.get('Sale Total')} != Grand Total {self.grand_total}")

    @allure.title("Validate via View Details - order-level totals")
    @allure.severity(allure.severity_level.NORMAL)
    def test_08_validate_view_details(self):
        sh = self.sales_history
        with allure.step("Actions -> View Details, check order number / customer / final grand total"):
            details = sh.open_order_details(self.order_no)
            assert details.is_shown(), "Order Details did not open"
            ok, missing = details.contains_all(
                self.order_no,
                self.customer_name,
                f"{self.grand_total:.2f}",
            )
            assert ok, f"Order Details missing expected values: {missing}"
            TestPromotionAdditionalDiscountStacking.sales_history = details.go_back()
