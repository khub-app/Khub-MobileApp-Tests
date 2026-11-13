"""Two overlapping Basic promotions (15% off and 25% off, same product,
same qty range) are both eligible on one cart line - the Admin app must
auto-apply the HIGHER discount (25%).

Mirrors khub-web-tests' UOM Promo Re-Pick scenario (PWkhubTest/UOM/
test_uom_promotion_repick_runner.py) for scenario intent only. That web test
goes on to switch between the two promotions via a "Promotions" picker
popover on the line, re-validating the real discounted price at each
switch. Confirmed live 2026-11-09 that this app's cart line has **no such
affordance**: dumping the line element's own attributes shows
`clickable="false"`, and no sibling button/icon exists near it - the cart
line is a single flattened, non-interactive View (same as every other cart
line in this app; see CLAUDE.md's "Most panels/rows are one flattened
element"). There is nothing to switch to or from - the engine silently
picks the higher discount and that's the only thing to verify here. Per
this task's own instructions ("do not assume the web app's UI patterns
exist here... say so rather than forcing a test to pass"), this test does
NOT attempt any switch/picker steps.

Mobile never creates the promotions/product itself - see
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
QTY = 1   # the scenario's own min_qty - both promos are eligible here


@allure.suite("Marketing Promotions")
@allure.feature("Promotions")
@allure.story("Promo Re-Pick - two overlapping promotions, the higher one auto-applies")
@pytest.mark.promotion
@pytest.mark.e2e
class TestPromotionRepick(MobileBaseSetup):

    # ---- shared context ----
    scenario = None
    customer_name = None
    sku = None
    piece_upc = None
    higher_promo_name = None
    higher_promo_percent = None
    base_price = None
    expected_discounted_price = None
    grand_total = None
    order_no = None

    sales_history = None
    cso = None
    cart_summary = None
    payment = None

    # ---------------------------------------------------------------- #
    @allure.title("Load the repick promotion scenario and resolve its product SKU")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_01_load_scenario_data(self):
        with allure.step("Read testdata/mobile_promotion_scenarios_<env>.json ('repick')"):
            scenario = promotion_data.get_scenario("repick", env=CFG["env"])
            TestPromotionRepick.scenario = scenario
            TestPromotionRepick.customer_name = scenario["customer"]
            TestPromotionRepick.piece_upc = scenario["product"]["piece_upc"]
            # The HIGHER of the two overlapping promotions is the one the
            # engine must auto-apply.
            higher = max(scenario["promotions"], key=lambda p: p["reward_percent"])
            TestPromotionRepick.higher_promo_name = higher["name"]
            TestPromotionRepick.higher_promo_percent = higher["reward_percent"]
        with allure.step("Resolve the product's SKU by UPC"):
            client = ApiClient()
            found = client.get_product_by_upc(self.piece_upc)
            assert found, f"Product with UPC {self.piece_upc} not found via backend search"
            TestPromotionRepick.sku = found["sku"]
            assert self.sku, f"Product {found} has no SKU"
            logger.info(f"Repick test: expecting the higher promo "
                        f"'{self.higher_promo_name}' ({self.higher_promo_percent}% off) "
                        f"to auto-apply over the other ({[p['reward_percent'] for p in scenario['promotions']]})")

    # ---------------- Part 1: open Sales History -> Create Sale Order --- #
    @allure.title("Open Sales History and start a new sale order")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_02_open_create_sale_order(self):
        with allure.step("Dashboard -> hamburger -> Sales History -> + FAB"):
            assert self.dashboard.is_loaded(), "Dashboard not shown"
            sh = self.dashboard.go_to_sales_history()
            assert sh.is_loaded(), "Sales History did not open"
            TestPromotionRepick.sales_history = sh
            TestPromotionRepick.cso = sh.tap_create_sale_order()
            assert self.cso.is_loaded(), "Create Sale Order page did not open"

    # ---------------- Part 2: customer + order info -------------------- #
    @allure.title("Add customer and order information")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_03_customer_and_order_info(self):
        name = self.customer_name
        with allure.step(f"Select API-created customer '{name}' and verify it is applied"):
            self.cso.select_customer(name)
            assert self.cso.is_customer_selected(name), f"Customer {name} not selected"
        with allure.step("Order Type = Online, add unique internal + invoice notes, Next"):
            self.cso.set_order_type(CFG["order_type"])
            self.cso.set_internal_note(f"{CFG['internal_note_prefix']}-repick")
            self.cso.set_invoice_note(f"{CFG['invoice_note_prefix']}-repick")
            self.cso.tap_next()
            assert self.cso.is_product_step_loaded(), "Did not reach the product-selection step"

    # ---------------- Part 3: add product, validate higher promo ------ #
    @allure.title("Add the product and confirm the HIGHER discount auto-applies")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_04_add_product_validate_higher_promo(self):
        with allure.step(f"Search + Add To Cart at qty={QTY}"):
            self.cso.add_product_by_sku(self.sku, qty=QTY, upc=self.piece_upc)
        with allure.step("The cart line names the HIGHER promotion and its percent"):
            line = self.cso.get_cart_line(self.sku, upc=self.piece_upc)
            assert_promo_state(line, True, "No promotion applied at all - ")
            assert line["promo_name"] == self.higher_promo_name, (
                f"Applied promo {line.get('promo_name')!r} != the higher one "
                f"{self.higher_promo_name!r}")
            assert line["promo_percent"] == self.higher_promo_percent, (
                f"Applied discount {line.get('promo_percent')}% != the higher "
                f"{self.higher_promo_percent}%")
        with allure.step("Discounted price = base price x (1 - higher%)"):
            base_price = money(line["sale_price"])
            TestPromotionRepick.base_price = base_price
            expected_discounted = money(
                base_price * (Decimal(100) - self.higher_promo_percent) / Decimal(100))
            TestPromotionRepick.expected_discounted_price = expected_discounted
            assert money(line["promo_original_price"]) == base_price, (
                f"Promo original price {line.get('promo_original_price')} != base price {base_price}")
            assert money(line["promo_discounted_price"]) == expected_discounted, (
                f"Discounted price {line.get('promo_discounted_price')} != {expected_discounted}")
            assert money(line["sub_total"]) == money(base_price * QTY), (
                f"Sub Total {line.get('sub_total')} != undiscounted {money(base_price * QTY)}")
            assert money(line["line_total"]) == money(expected_discounted * QTY), (
                f"Total {line.get('line_total')} != {money(expected_discounted * QTY)}")
            allure.attach(str(line), name="Cart line (repick)", attachment_type=allure.attachment_type.TEXT)
        with allure.step("Next -> Cart Summary"):
            TestPromotionRepick.cart_summary = self.cso.tap_next_to_summary()

    # ---------------- Part 4: validate the cart summary --------------- #
    @allure.title("Validate Cart Summary: discounted total reflects the higher promo")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_05_validate_cart_summary(self):
        cs = self.cart_summary
        expected_total = money(self.expected_discounted_price * QTY)
        with allure.step("Discounted Sub Total, Promo Savings, Grand Total"):
            cs.scroll_to_summary()
            assert cs.get_total_quantity() == QTY, f"Total Quantity != {QTY}"
            assert money(cs.get_sub_total()) == expected_total, (
                f"Cart Summary Sub Total {cs.get_sub_total()} != {expected_total}")
            expected_savings = money(self.base_price * QTY) - expected_total
            promo_savings = money(abs(cs.get_promo_savings()))
            assert promo_savings == money(expected_savings), (
                f"Promo Savings {promo_savings} != expected {expected_savings}")
            tax = money(cs.get_tax())
            TestPromotionRepick.grand_total = money(cs.get_grand_total())
            assert self.grand_total == money(expected_total + tax), (
                f"Grand Total {self.grand_total} != {expected_total} + tax {tax}")
        with allure.step("Proceed to Checkout"):
            TestPromotionRepick.payment = cs.proceed_to_checkout()

    # ---------------- Part 5: complete the sale with cash ------------- #
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
            TestPromotionRepick.sales_history = pay.tap_ok_return_to_sales_history()

    # ---------------- Part 6: validate in Sales History -------------- #
    @allure.title("Validate the new order in Sales History and capture its number")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_07_validate_sales_history(self):
        sh = self.sales_history
        with allure.step("Locate the newest card for this customer, capture Order Number"):
            order_no = sh.capture_latest_order_no(self.customer_name)
            assert order_no.startswith("SO-"), f"Order number {order_no!r} not in SO- format"
            TestPromotionRepick.order_no = order_no
        with allure.step("Card: customer / Online / Paid / Sale Total == discounted Grand Total"):
            card = sh.get_order_card(order_no)
            assert card.get("Business Name", "").strip() == self.customer_name, "Business Name mismatch"
            assert card.get("Order Type") == "Online", f"Order Type = {card.get('Order Type')!r}"
            assert card.get("Invoice Status") == "Paid", f"Invoice Status = {card.get('Invoice Status')!r}"
            assert money(parse_currency(card.get("Sale Total", "0"))) == self.grand_total, (
                f"Sale Total {card.get('Sale Total')} != Grand Total {self.grand_total}")

    @allure.title("Validate via View Details - order-level totals")
    @allure.severity(allure.severity_level.NORMAL)
    def test_08_validate_view_details(self):
        # Order-level totals only - View Details' own per-line "Extended"
        # field is known to miscompute a discounted line (confirmed live in
        # test_promotion_multi_tier.py: wrong sign on the discount percent,
        # ignores Order Qty), so it is not asserted on here either.
        sh = self.sales_history
        with allure.step("Actions -> View Details, check order number / customer / grand total"):
            details = sh.open_order_details(self.order_no)
            assert details.is_shown(), "Order Details did not open"
            ok, missing = details.contains_all(
                self.order_no,
                self.customer_name,
                f"{self.grand_total:.2f}",
            )
            assert ok, f"Order Details missing expected values: {missing}"
            TestPromotionRepick.sales_history = details.go_back()
