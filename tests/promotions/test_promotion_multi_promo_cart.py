"""Multiple INDEPENDENT promotions applied simultaneously in one cart - the
normal production case (a real order usually has more than one promoted
item), but never exercised by any other promotion test here: every other
scenario has exactly one discount-relevant line (or trigger/reward pair).

Reuses products from 3 of the already-generated scenarios (no new
promotion/product data needed - each is independently eligible on its own
terms) in ONE order for ONE customer:
  - multi_tier's product, Piece tier, qty=2 -> 20% off (Basic)
  - phase2_boundary's product, qty=3 -> 20% off (Basic, a different promo)
  - bxgy's trigger (qty=2, undiscounted) + reward (qty=1, 50% off, a
    DIFFERENT product again)
Cart Summary's "Promo Savings" must equal the SUM of all three independent
discounts, and Sub Total must equal the sum of every line's real charged
Total - not just reflect whichever discount happened to apply last.

None of our scenario promotions restrict eligibility by customer or
channel (`applicable_for`/`customer_group_ids` are the unrestricted
"all customers" shape in every one `create_mobile_promotion_scenarios_api.py`
builds), so any one scenario's customer can buy any other scenario's
promoted product - confirmed by this test actually doing so.

Mobile never creates the promotion/products itself - see
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

logger = get_logger(__name__)

with open("data/test_data.yaml", "r", encoding="utf-8") as f:
    TEST_DATA = yaml.safe_load(f)

CFG = TEST_DATA["promotion_sale"]


@allure.feature("Promotions")
@allure.story("Multiple independent promotions in one cart - Promo Savings sums all of them")
@pytest.mark.promotion
@pytest.mark.e2e
class TestPromotionMultiPromoCart(MobileBaseSetup):

    # ---- shared context ----
    customer_name = None
    lines = None   # list of dicts, one per cart line, filled in as we go

    expected_discounted_total = None
    expected_undiscounted_total = None
    expected_savings = None
    grand_total = None
    order_no = None

    sales_history = None
    cso = None
    cart_summary = None
    payment = None

    # ---------------------------------------------------------------- #
    @allure.title("Load 3 independent scenarios' data and resolve every SKU")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_01_load_scenario_data(self):
        client = ApiClient()
        with allure.step("Read multi_tier, phase2_boundary, bxgy from the scenario data file"):
            multi_tier = promotion_data.get_scenario("multi_tier", env=CFG["env"])
            phase2 = promotion_data.get_scenario("phase2_boundary", env=CFG["env"])
            bxgy = promotion_data.get_scenario("bxgy", env=CFG["env"])
            # Use multi_tier's customer for the whole order - none of these
            # promotions restrict eligibility by customer/channel.
            TestPromotionMultiPromoCart.customer_name = multi_tier["customer"]

        def resolve(upc):
            found = client.get_product_by_upc(upc)
            assert found, f"Product with UPC {upc} not found via backend search"
            return found["sku"]

        with allure.step("Resolve SKUs for all 4 products across the 3 promotions"):
            TestPromotionMultiPromoCart.lines = [
                {"label": "multi_tier (Basic 20% off)", "sku": resolve(multi_tier["product"]["piece_upc"]),
                 "upc": multi_tier["product"]["piece_upc"], "qty": 2,
                 "promo_name": multi_tier["promotion"]["name"], "promo_percent": multi_tier["params"]["reward_percent"],
                 "role": "basic"},
                {"label": "phase2_boundary (Basic 20% off)", "sku": resolve(phase2["product"]["piece_upc"]),
                 "upc": phase2["product"]["piece_upc"], "qty": 3,
                 "promo_name": None, "promo_percent": phase2["params"]["reward_percent"],  # either of its 2 promos may show
                 "role": "basic"},
                {"label": "bxgy trigger (undiscounted)", "sku": resolve(bxgy["trigger_product"]["piece_upc"]),
                 "upc": bxgy["trigger_product"]["piece_upc"], "qty": bxgy["params"]["trigger_qty"],
                 "promo_name": bxgy["promotion"]["name"], "role": "bxgy_trigger"},
                {"label": "bxgy reward (50% off)", "sku": resolve(bxgy["reward_product"]["piece_upc"]),
                 "upc": bxgy["reward_product"]["piece_upc"], "qty": 1,
                 "promo_name": bxgy["promotion"]["name"], "promo_percent": bxgy["params"]["reward_percent"],
                 "role": "bxgy_reward"},
            ]
            for l in self.lines:
                logger.info(f"Line: {l['label']} SKU={l['sku']} qty={l['qty']}")

    # ---------------- Part 1: open Sales History -> Create Sale Order --- #
    @allure.title("Open Sales History and start a new sale order")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_02_open_create_sale_order(self):
        with allure.step("Dashboard -> hamburger -> Sales History -> + FAB"):
            assert self.dashboard.is_loaded(), "Dashboard not shown"
            sh = self.dashboard.go_to_sales_history()
            assert sh.is_loaded(), "Sales History did not open"
            TestPromotionMultiPromoCart.sales_history = sh
            TestPromotionMultiPromoCart.cso = sh.tap_create_sale_order()
            assert self.cso.is_loaded(), "Create Sale Order page did not open"

    # ---------------- Part 2: customer + order info -------------------- #
    @allure.title("Add customer and order information")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_03_customer_and_order_info(self):
        name = self.customer_name
        with allure.step(f"Select customer '{name}' (from multi_tier's scenario) and verify"):
            self.cso.select_customer(name)
            assert self.cso.is_customer_selected(name), f"Customer {name} not selected"
        with allure.step("Order Type = Online, add unique internal + invoice notes, Next"):
            self.cso.set_order_type(CFG["order_type"])
            self.cso.set_internal_note(f"{CFG['internal_note_prefix']}-multi-promo")
            self.cso.set_invoice_note(f"{CFG['invoice_note_prefix']}-multi-promo")
            self.cso.tap_next()
            assert self.cso.is_product_step_loaded(), "Did not reach the product-selection step"

    # ---------------- Part 3: add all 4 lines, validate each independently #
    @allure.title("Add all 4 lines (3 independent promotions) and validate each one")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_04_add_all_lines_validate_each_promo(self):
        for l in self.lines:
            with allure.step(f"Add {l['label']} at qty={l['qty']}"):
                self.cso.add_product_by_sku(l["sku"], qty=l["qty"], upc=l["upc"])

        discounted_total = Decimal("0.00")
        undiscounted_total = Decimal("0.00")
        for l in self.lines:
            with allure.step(f"Validate '{l['label']}'"):
                line = self.cso.get_cart_line(l["sku"], upc=l["upc"])
                base_price = money(line["sale_price"])
                full_total = money(base_price * l["qty"])
                undiscounted_total += full_total

                if l["role"] == "bxgy_trigger":
                    assert not line["is_promo_active"], f"BXGY trigger line should never be discounted: {line}"
                    assert money(line["line_total"]) == full_total
                    discounted_total += full_total
                else:
                    assert line["is_promo_active"], f"'{l['label']}' expected to be discounted: {line}"
                    if l.get("promo_name"):
                        assert line["promo_name"] == l["promo_name"], (
                            f"'{l['label']}' promo name {line.get('promo_name')!r} != {l['promo_name']!r}")
                    assert line["promo_percent"] == l["promo_percent"], (
                        f"'{l['label']}' discount {line.get('promo_percent')}% != {l['promo_percent']}%")
                    expected_discounted_price = money(
                        base_price * (Decimal(100) - l["promo_percent"]) / Decimal(100))
                    expected_line_total = money(expected_discounted_price * l["qty"])
                    assert money(line["line_total"]) == expected_line_total, (
                        f"'{l['label']}' Total {line.get('line_total')} != {expected_line_total}")
                    l["savings"] = full_total - expected_line_total
                    discounted_total += expected_line_total

        TestPromotionMultiPromoCart.expected_discounted_total = money(discounted_total)
        TestPromotionMultiPromoCart.expected_undiscounted_total = money(undiscounted_total)
        TestPromotionMultiPromoCart.expected_savings = money(undiscounted_total - discounted_total)
        logger.info(f"Undiscounted total=${undiscounted_total} discounted total=${discounted_total} "
                    f"expected Promo Savings=${self.expected_savings}")
        with allure.step("Next -> Cart Summary"):
            TestPromotionMultiPromoCart.cart_summary = self.cso.tap_next_to_summary()

    # ---------------- Part 4: validate the cart summary ----------------- #
    @allure.title("Validate Cart Summary: Promo Savings sums all 3 independent promotions")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_05_validate_cart_summary(self):
        cs = self.cart_summary
        expected_qty = sum(l["qty"] for l in self.lines)
        with allure.step("Total quantity, discounted Sub Total, aggregate Promo Savings, Grand Total"):
            cs.scroll_to_summary()
            assert cs.get_total_quantity() == expected_qty, "Total Quantity mismatch across all 4 lines"
            assert money(cs.get_sub_total()) == self.expected_discounted_total, (
                f"Cart Summary Sub Total {cs.get_sub_total()} != {self.expected_discounted_total}")
            assert money(cs.get_additional_discount()) == money(0), "Additional Discount is not $0.00"

            promo_savings = money(abs(cs.get_promo_savings()))
            assert promo_savings == self.expected_savings, (
                f"Promo Savings {promo_savings} != expected {self.expected_savings} "
                f"(sum of multi_tier's 20% off + phase2_boundary's 20% off + bxgy's 50% off reward)")

            tax = money(cs.get_tax())
            TestPromotionMultiPromoCart.grand_total = money(cs.get_grand_total())
            assert self.grand_total == money(self.expected_discounted_total + tax), (
                f"Grand Total {self.grand_total} != discounted subtotal "
                f"{self.expected_discounted_total} + tax {tax}")
        with allure.step("Proceed to Checkout"):
            TestPromotionMultiPromoCart.payment = cs.proceed_to_checkout()

    # ---------------- Part 5: complete the sale with cash ---------------- #
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
            TestPromotionMultiPromoCart.sales_history = pay.tap_ok_return_to_sales_history()

    # ---------------- Part 6: validate in Sales History ------------------ #
    @allure.title("Validate the new order in Sales History and capture its number")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_07_validate_sales_history(self):
        sh = self.sales_history
        with allure.step("Locate the newest card for this customer, capture Order Number"):
            order_no = sh.capture_latest_order_no(self.customer_name)
            assert order_no.startswith("SO-"), f"Order number {order_no!r} not in SO- format"
            TestPromotionMultiPromoCart.order_no = order_no
        with allure.step("Card: customer / Online / Paid / Sale Total == combined discounted Grand Total"):
            card = sh.get_order_card(order_no)
            assert card.get("Business Name", "").strip() == self.customer_name, "Business Name mismatch"
            assert card.get("Order Type") == "Online", f"Order Type = {card.get('Order Type')!r}"
            assert card.get("Invoice Status") == "Paid", f"Invoice Status = {card.get('Invoice Status')!r}"
            assert money(parse_currency(card.get("Sale Total", "0"))) == self.grand_total, (
                f"Sale Total {card.get('Sale Total')} != Grand Total {self.grand_total}")

    @allure.title("Validate via View Details - order-level totals")
    @allure.severity(allure.severity_level.NORMAL)
    def test_08_validate_view_details(self):
        # Order-level totals only - View Details' per-line "Extended" field
        # is known to miscompute discounted lines (confirmed live in
        # test_promotion_multi_tier.py), not asserted on here either.
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
            TestPromotionMultiPromoCart.sales_history = details.go_back()
