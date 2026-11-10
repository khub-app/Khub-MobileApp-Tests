"""A promotion scoped to a specific Customer Group must discount for a
customer IN that group and must NOT discount the exact same product for a
customer who is NOT a member - a real business-risk guarantee ("don't give
the discount to someone who shouldn't get it") that no other promotion test
here exercises: every other scenario's promotion uses the broadest
"applies to everyone" scope.

Unlike every other scenario, the Customer Group + its one member/one
non-member customer here are a STABLE, manually-provisioned fixture, not
created fresh by the API script - no API endpoint for creating a Customer
Group was found (browser network capture against the real portal's
"Create Customer Group" flow on 2026-11-10 did not surface it). The
PRODUCT and PROMOTION are still fresh every run, scoped via the confirmed
`POST /tenant/api/v1/marketing/promotions` shape (`applicable_to: 3`,
`customer_group_ids: [<group id>]`) - captured by creating one through the
real portal UI and reading it back via `GET .../marketing/promotions/list`.
See `create_mobile_promotion_scenarios_api.py`'s `_scenario_customer_targeting`
docstring for exactly how to recreate the group fixture if it's ever
deleted.

Confirmed live 2026-11-10: the out-of-group customer's line is completely
plain - no banner, no discounted-price pair, and (same as a temporally-
ineligible promotion in test_promotion_validity_window.py) not even a
"Range:" indicator. A customer-ineligible promotion leaves no trace on the
line at all, same as a time-ineligible one.

Mobile never creates the promotion/product itself - see
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

logger = get_logger(__name__)

with open("data/test_data.yaml", "r", encoding="utf-8") as f:
    TEST_DATA = yaml.safe_load(f)

CFG = TEST_DATA["promotion_sale"]
QTY = 2


@allure.feature("Promotions")
@allure.story("A promotion scoped to a Customer Group only discounts for members of that group")
@pytest.mark.promotion
@pytest.mark.e2e
class TestPromotionCustomerTargeting(MobileBaseSetup):

    # ---- shared context ----
    scenario = None
    sku = None
    piece_upc = None
    promo_name = None
    reward_percent = None
    in_group_customer = None
    out_of_group_customer = None

    grand_total = None
    order_no = None

    sales_history = None
    cso = None
    cart_summary = None
    payment = None

    # ---------------------------------------------------------------- #
    @allure.title("Load the customer_targeting scenario and resolve its product SKU")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_01_load_scenario_data(self):
        with allure.step("Read testdata/mobile_promotion_scenarios_<env>.json ('customer_targeting')"):
            scenario = promotion_data.get_scenario("customer_targeting", env=CFG["env"])
            TestPromotionCustomerTargeting.scenario = scenario
            params = scenario["params"]
            TestPromotionCustomerTargeting.piece_upc = scenario["product"]["piece_upc"]
            TestPromotionCustomerTargeting.promo_name = scenario["promotion"]["name"]
            TestPromotionCustomerTargeting.reward_percent = params["reward_percent"]
            TestPromotionCustomerTargeting.in_group_customer = scenario["in_group_customer"]
            TestPromotionCustomerTargeting.out_of_group_customer = scenario["out_of_group_customer"]
            logger.info(f"'{self.promo_name}' ({self.reward_percent}% off) scoped to a customer group - "
                        f"must apply for '{self.in_group_customer}', must NOT apply for "
                        f"'{self.out_of_group_customer}'")
        with allure.step("Resolve the product's SKU by UPC"):
            client = ApiClient()
            found = client.get_product_by_upc(self.piece_upc)
            assert found, f"Product with UPC {self.piece_upc} not found via backend search"
            TestPromotionCustomerTargeting.sku = found["sku"]

    # -------------- helper (not a test) -------------- #
    def _open_fresh_order_to_product_step(self, customer_name, note_suffix=None):
        sh = self.dashboard.go_to_sales_history()
        assert sh.is_loaded(), "Sales History did not open"
        cso = sh.tap_create_sale_order()
        assert cso.is_loaded(), "Create Sale Order page did not open"
        cso.select_customer(customer_name)
        assert cso.is_customer_selected(customer_name), f"Customer {customer_name} not selected"
        cso.set_order_type(CFG["order_type"])
        if note_suffix:
            cso.set_internal_note(f"{CFG['internal_note_prefix']}-{note_suffix}")
            cso.set_invoice_note(f"{CFG['invoice_note_prefix']}-{note_suffix}")
        cso.tap_next()
        assert cso.is_product_step_loaded(), "Did not reach the product-selection step"
        return cso

    # ---------------- Part 1: the out-of-group customer gets NO discount - #
    @allure.title("Out-of-group customer: same product, same qty, NO discount")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_02_out_of_group_customer_no_discount(self):
        with allure.step(f"Fresh order for '{self.out_of_group_customer}' (NOT a group member)"):
            cso = self._open_fresh_order_to_product_step(self.out_of_group_customer)
            cso.add_product_by_sku(self.sku, qty=QTY, upc=self.piece_upc)
            line = cso.get_cart_line(self.sku, upc=self.piece_upc)
            assert not line["is_promo_active"], (
                f"Out-of-group customer '{self.out_of_group_customer}' was discounted - "
                f"promotion leaked outside its Customer Group: {line}")
            assert "promo_name" not in line, (
                f"Out-of-group customer's line shows a promo tag at all (expected none): {line}")
            expected_full = money(line["sale_price"] * QTY)
            assert money(line["sub_total"]) == expected_full
            assert money(line["line_total"]) == expected_full, (
                f"Out-of-group Total {line.get('line_total')} != full price {expected_full}")
            cso.discard_order()

    # ---------------- Part 2: the in-group customer DOES get the discount - #
    @allure.title("In-group customer: same product, same qty, discount applies")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_03_open_in_group_order_validate_discount(self):
        with allure.step(f"Fresh order for '{self.in_group_customer}' (a group member) - keep this one open"):
            cso = self._open_fresh_order_to_product_step(self.in_group_customer, note_suffix="customer-targeting")
            cso.add_product_by_sku(self.sku, qty=QTY, upc=self.piece_upc)
            TestPromotionCustomerTargeting.cso = cso
        with allure.step("Line is discounted, same promo/percent as configured"):
            line = cso.get_cart_line(self.sku, upc=self.piece_upc)
            assert line["is_promo_active"], (
                f"In-group customer '{self.in_group_customer}' was NOT discounted: {line}")
            assert line["promo_name"] == self.promo_name
            assert line["promo_percent"] == self.reward_percent
            from decimal import Decimal
            base_price = money(line["sale_price"])
            expected_discounted = money(base_price * (Decimal(100) - self.reward_percent) / Decimal(100))
            assert money(line["promo_discounted_price"]) == expected_discounted, (
                f"Discounted price {line.get('promo_discounted_price')} != {expected_discounted}")
            assert money(line["line_total"]) == money(expected_discounted * QTY), (
                f"Total {line.get('line_total')} != {money(expected_discounted * QTY)}")
        with allure.step("Next -> Cart Summary"):
            TestPromotionCustomerTargeting.cart_summary = cso.tap_next_to_summary()

    # ---------------- Part 3: validate the cart summary ------------------ #
    @allure.title("Validate Cart Summary for the in-group customer's discounted order")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_04_validate_cart_summary(self):
        cs = self.cart_summary
        with allure.step("Discounted Sub Total, non-zero Promo Savings, Grand Total"):
            cs.scroll_to_summary()
            assert cs.get_total_quantity() == QTY, f"Total Quantity != {QTY}"
            promo_savings = money(abs(cs.get_promo_savings()))
            assert promo_savings > money(0), "Promo Savings should be non-zero for the in-group customer"
            tax = money(cs.get_tax())
            TestPromotionCustomerTargeting.grand_total = money(cs.get_grand_total())
            expected_subtotal = money(cs.get_sub_total())
            assert self.grand_total == money(expected_subtotal + tax), (
                f"Grand Total {self.grand_total} != Sub Total {expected_subtotal} + tax {tax}")
        with allure.step("Proceed to Checkout"):
            TestPromotionCustomerTargeting.payment = cs.proceed_to_checkout()

    # ---------------- Part 4: complete the sale with cash ----------------- #
    @allure.title("Pay in full with Cash and complete the sale")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_05_complete_cash_sale(self):
        pay = self.payment
        with allure.step("Invoice Total == Grand Total; correct customer"):
            assert pay.is_loaded(), "Payment page not shown"
            assert money(pay.get_invoice_total()) == self.grand_total, "Invoice Total != captured Grand Total"
            assert self.in_group_customer in pay.get_customer(), "Payment page shows the wrong customer"
        with allure.step("Select Cash; amount is the full invoice total"):
            pay.select_cash()
            assert money(pay.get_amount()) == self.grand_total, "Cash amount != Grand Total"
        with allure.step("Complete Sale -> success dialog -> OK"):
            pay.complete_sale()
            msg = pay.wait_success_dialog()
            assert "saved successfully" in msg, f"Unexpected success message: {msg!r}"
            TestPromotionCustomerTargeting.sales_history = pay.tap_ok_return_to_sales_history()

    # ---------------- Part 5: validate in Sales History -------------------- #
    @allure.title("Validate the in-group customer's order in Sales History")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_06_validate_sales_history(self):
        sh = self.sales_history
        with allure.step("Locate the newest card for the in-group customer, capture Order Number"):
            order_no = sh.capture_latest_order_no(self.in_group_customer)
            assert order_no.startswith("SO-"), f"Order number {order_no!r} not in SO- format"
            TestPromotionCustomerTargeting.order_no = order_no
        with allure.step("Card: customer / Online / Paid / Sale Total == discounted Grand Total"):
            card = sh.get_order_card(order_no)
            assert card.get("Business Name", "").strip() == self.in_group_customer, "Business Name mismatch"
            assert card.get("Order Type") == "Online", f"Order Type = {card.get('Order Type')!r}"
            assert card.get("Invoice Status") == "Paid", f"Invoice Status = {card.get('Invoice Status')!r}"
            assert money(parse_currency(card.get("Sale Total", "0"))) == self.grand_total, (
                f"Sale Total {card.get('Sale Total')} != Grand Total {self.grand_total}")
