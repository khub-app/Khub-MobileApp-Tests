"""Verify a Basic promotion's qty-range boundary on the Admin app's cart:
two identical promotions (min_qty=2, max_reward_qty=5, 20% off) sit on the
same product's Piece tier; the discount must be OFF at qty 1 and 6, and ON
at qty 2, 3, 5.

Mirrors khub-web-tests' UOM promotion Phase-2 scenario (PWkhubTest/UOM/
test_uom_promotion_phase2_sale_runner.py) for scenario intent only. That web
test edits ONE cart line's qty in place across the whole boundary matrix -
this app has no way to do that (Order Qty on an already-placed line is a
read-only View, confirmed by the existing UOM gotchas and re-confirmed here
live 2026-11-09 against this exact promoted line), so each boundary qty is
checked on its OWN fresh order (CreateSaleOrderPage.discard_order() backs
out cleanly without completing it) - except the first in-range qty (the
promo's own min_qty), whose order is carried through to a full Cash sale +
Sales History + View Details check, same depth as test_promotion_multi_tier.py.

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


@allure.suite("Marketing Promotions")
@allure.feature("Promotions")
@allure.story("Phase 2 - qty-range boundary (on at 2/3/5, off at 1/6)")
@pytest.mark.promotion
@pytest.mark.e2e
class TestPromotionPhase2Boundary(MobileBaseSetup):

    # ---- shared context ----
    scenario = None
    customer_name = None
    sku = None
    piece_upc = None
    promo_names = None     # both promotion names - either may be the one the app shows
    reward_percent = None
    qty_min = None
    qty_max = None

    base_price = None                   # Decimal, filled in test_06 from the live cart line
    expected_discounted_price = None   # Decimal, filled in test_01
    grand_total = None
    order_no = None

    sales_history = None
    cso = None
    cart_summary = None
    payment = None

    # ---------------------------------------------------------------- #
    @allure.title("Load the phase2_boundary promotion scenario and resolve its product SKU")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_01_load_scenario_data(self):
        with allure.step("Read testdata/mobile_promotion_scenarios_<env>.json ('phase2_boundary')"):
            scenario = promotion_data.get_scenario("phase2_boundary", env=CFG["env"])
            TestPromotionPhase2Boundary.scenario = scenario
            params = scenario["params"]
            TestPromotionPhase2Boundary.customer_name = scenario["customer"]
            TestPromotionPhase2Boundary.piece_upc = scenario["product"]["piece_upc"]
            TestPromotionPhase2Boundary.promo_names = {p["name"] for p in scenario["promotions"]}
            TestPromotionPhase2Boundary.reward_percent = params["reward_percent"]
            TestPromotionPhase2Boundary.qty_min = params["min_qty"]
            TestPromotionPhase2Boundary.qty_max = params["max_reward_qty"]
        with allure.step("Resolve the product's SKU by UPC"):
            client = ApiClient()
            found = client.get_product_by_upc(self.piece_upc)
            assert found, f"Product with UPC {self.piece_upc} not found via backend search"
            TestPromotionPhase2Boundary.sku = found["sku"]
            assert self.sku, f"Product {found} has no SKU"
            logger.info(f"Boundary test: qty range [{self.qty_min},{self.qty_max}], "
                        f"{self.reward_percent}% off, SKU={self.sku}, promos={self.promo_names}")

    # -------------- helper (not a test) -------------- #
    def _open_fresh_order_to_product_step(self, note_suffix: str | None = None):
        sh = self.dashboard.go_to_sales_history()
        assert sh.is_loaded(), "Sales History did not open"
        cso = sh.tap_create_sale_order()
        assert cso.is_loaded(), "Create Sale Order page did not open"
        cso.select_customer(self.customer_name)
        assert cso.is_customer_selected(self.customer_name), f"Customer {self.customer_name} not selected"
        cso.set_order_type(CFG["order_type"])
        if note_suffix:
            cso.set_internal_note(f"{CFG['internal_note_prefix']}-{note_suffix}")
            cso.set_invoice_note(f"{CFG['invoice_note_prefix']}-{note_suffix}")
        cso.tap_next()
        assert cso.is_product_step_loaded(), "Did not reach the product-selection step"
        return cso

    def _assert_boundary_line(self, qty: int, in_range: bool, line: dict):
        base_price = money(line["sale_price"])
        TestPromotionPhase2Boundary.base_price = base_price
        expected_undiscounted = money(base_price * qty)
        assert money(line["sub_total"]) == expected_undiscounted, (
            f"qty={qty}: Sub Total {line.get('sub_total')} != {expected_undiscounted}")
        assert_promo_state(line, in_range, (
            f"qty={qty}: qty is {'inside' if in_range else 'outside'} "
            f"[{self.qty_min},{self.qty_max}] - "))
        if in_range:
            assert line["promo_name"] in self.promo_names, (
                f"qty={qty}: promo name {line.get('promo_name')!r} not one of {self.promo_names}")
            assert line["promo_percent"] == self.reward_percent, (
                f"qty={qty}: promo percent {line.get('promo_percent')} != {self.reward_percent}")
            expected_discounted_price = money(
                base_price * (Decimal(100) - self.reward_percent) / Decimal(100))
            if TestPromotionPhase2Boundary.expected_discounted_price is None:
                TestPromotionPhase2Boundary.expected_discounted_price = expected_discounted_price
            assert money(line["promo_discounted_price"]) == expected_discounted_price, (
                f"qty={qty}: discounted price {line.get('promo_discounted_price')} != "
                f"{expected_discounted_price}")
            assert money(line["line_total"]) == money(expected_discounted_price * qty), (
                f"qty={qty}: Total {line.get('line_total')} != "
                f"{money(expected_discounted_price * qty)}")
        else:
            assert money(line["line_total"]) == expected_undiscounted, (
                f"qty={qty}: out of range but Total {line.get('line_total')} != "
                f"undiscounted {expected_undiscounted}")
        assert line.get("promo_qty_min") == self.qty_min and line.get("promo_qty_max") == self.qty_max, (
            f"qty={qty}: displayed promo range != [{self.qty_min},{self.qty_max}]: {line}")

    # -------------- below-range / mid-range / at-max / above-range --- #
    @allure.title("qty 1 (below min_qty) - discount must NOT apply")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_02_qty_below_min_not_eligible(self):
        qty = 1
        with allure.step(f"Fresh order, add product at qty={qty}, validate, then discard"):
            cso = self._open_fresh_order_to_product_step()
            cso.add_product_by_sku(self.sku, qty=qty, upc=self.piece_upc)
            line = cso.get_cart_line(self.sku, upc=self.piece_upc)
            self._assert_boundary_line(qty, in_range=False, line=line)
            TestPromotionPhase2Boundary.sales_history = cso.discard_order()

    @allure.title("qty 3 (mid-range) - discount must apply")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_03_qty_mid_range_eligible(self):
        qty = 3
        with allure.step(f"Fresh order, add product at qty={qty}, validate, then discard"):
            cso = self._open_fresh_order_to_product_step()
            cso.add_product_by_sku(self.sku, qty=qty, upc=self.piece_upc)
            line = cso.get_cart_line(self.sku, upc=self.piece_upc)
            self._assert_boundary_line(qty, in_range=True, line=line)
            TestPromotionPhase2Boundary.sales_history = cso.discard_order()

    @allure.title("qty 5 (at max_reward_qty) - discount must apply")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_04_qty_at_max_eligible(self):
        qty = 5
        with allure.step(f"Fresh order, add product at qty={qty}, validate, then discard"):
            cso = self._open_fresh_order_to_product_step()
            cso.add_product_by_sku(self.sku, qty=qty, upc=self.piece_upc)
            line = cso.get_cart_line(self.sku, upc=self.piece_upc)
            self._assert_boundary_line(qty, in_range=True, line=line)
            TestPromotionPhase2Boundary.sales_history = cso.discard_order()

    @allure.title("qty 6 (above max_reward_qty) - discount must NOT apply")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_05_qty_above_max_not_eligible(self):
        qty = 6
        with allure.step(f"Fresh order, add product at qty={qty}, validate, then discard"):
            cso = self._open_fresh_order_to_product_step()
            cso.add_product_by_sku(self.sku, qty=qty, upc=self.piece_upc)
            line = cso.get_cart_line(self.sku, upc=self.piece_upc)
            self._assert_boundary_line(qty, in_range=False, line=line)
            TestPromotionPhase2Boundary.sales_history = cso.discard_order()

    # -------------- qty 2 (at min_qty) - carried through to a real sale - #
    @allure.title("qty 2 (at min_qty) - discount applies; carry this order through checkout")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_06_open_eligible_order_qty_at_min(self):
        qty = 2
        with allure.step(f"Fresh order, add product at qty={qty}, validate - keep this one open"):
            cso = self._open_fresh_order_to_product_step(note_suffix="phase2-boundary")
            cso.add_product_by_sku(self.sku, qty=qty, upc=self.piece_upc)
            line = cso.get_cart_line(self.sku, upc=self.piece_upc)
            self._assert_boundary_line(qty, in_range=True, line=line)
            TestPromotionPhase2Boundary.cso = cso
        with allure.step("Next -> Cart Summary"):
            TestPromotionPhase2Boundary.cart_summary = self.cso.tap_next_to_summary()

    @allure.title("Validate Cart Summary for the qty=2 eligible order")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_07_validate_cart_summary(self):
        cs = self.cart_summary
        expected_total = money(self.expected_discounted_price * 2)
        with allure.step("Discounted Sub Total, Promo Savings, Grand Total"):
            cs.scroll_to_summary()
            assert cs.get_total_quantity() == 2, "Total Quantity != 2"
            assert money(cs.get_sub_total()) == expected_total, (
                f"Cart Summary Sub Total {cs.get_sub_total()} != {expected_total}")
            expected_savings = money(self.base_price * 2) - expected_total
            promo_savings = money(abs(cs.get_promo_savings()))
            assert promo_savings == money(expected_savings), (
                f"Promo Savings {promo_savings} != expected {expected_savings}")
            tax = money(cs.get_tax())
            TestPromotionPhase2Boundary.grand_total = money(cs.get_grand_total())
            assert self.grand_total == money(expected_total + tax), (
                f"Grand Total {self.grand_total} != {expected_total} + tax {tax}")
        with allure.step("Proceed to Checkout"):
            TestPromotionPhase2Boundary.payment = cs.proceed_to_checkout()

    @allure.title("Pay in full with Cash and complete the sale")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_08_complete_cash_sale(self):
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
            TestPromotionPhase2Boundary.sales_history = pay.tap_ok_return_to_sales_history()

    @allure.title("Validate the qty=2 order in Sales History")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_09_validate_sales_history(self):
        sh = self.sales_history
        with allure.step("Locate the newest card for this customer, capture Order Number"):
            order_no = sh.capture_latest_order_no(self.customer_name)
            assert order_no.startswith("SO-"), f"Order number {order_no!r} not in SO- format"
            TestPromotionPhase2Boundary.order_no = order_no
        with allure.step("Card: customer / Online / Paid / Sale Total == discounted Grand Total"):
            card = sh.get_order_card(order_no)
            assert card.get("Business Name", "").strip() == self.customer_name, "Business Name mismatch"
            assert card.get("Order Type") == "Online", f"Order Type = {card.get('Order Type')!r}"
            assert card.get("Invoice Status") == "Paid", f"Invoice Status = {card.get('Invoice Status')!r}"
            assert money(parse_currency(card.get("Sale Total", "0"))) == self.grand_total, (
                f"Sale Total {card.get('Sale Total')} != Grand Total {self.grand_total}")

    @allure.title("Validate via View Details - order-level totals")
    @allure.severity(allure.severity_level.NORMAL)
    def test_10_validate_view_details(self):
        # Only order-level totals are checked here, not the single line's
        # own "Extended" field - confirmed in test_promotion_multi_tier.py
        # that View Details miscomputes "Extended" for a discounted line
        # (wrong sign on the discount percent, ignores Order Qty). See that
        # test's module/step comments for the full live evidence.
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
            TestPromotionPhase2Boundary.sales_history = details.go_back()
