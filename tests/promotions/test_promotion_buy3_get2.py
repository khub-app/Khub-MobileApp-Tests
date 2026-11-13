"""BXGY variant: buy 3 of a trigger product, get 2 units of a DIFFERENT
reward product at 50% off - same mechanism as test_promotion_bxgy.py
(different trigger_qty/max_reward_qty: 3/2 instead of 2/5), but this test
additionally exercises the reward-qty upper boundary that scenario never
reached (its reward qty was always 1, well under its max of 5).

Two live findings not covered by test_promotion_bxgy.py, both confirmed
2026-11-09:
- A self-referential version of this ("buy 3 of ONE product, 2 of those 3
  units at 50% off") was tried first and does NOT work: with trigger and
  reward pointing at the same product/unit, the single resulting cart line
  shows the promotion's name with a bare "trigger" tag and NO discount at
  all, even once qty meets trigger_qty. The reward mechanism needs a
  structurally separate line to attach its discount to - there's nowhere
  for it to render when trigger_sources == reward_sources. So, like the
  cross-product `bxgy` scenario, this one uses two distinct products (see
  khub-web-tests' create_mobile_promotion_scenarios_api.py's
  `_scenario_buy3_get2_half_off` / `BUY3GET2_*` constants for the full
  finding).
- The reward line's qty vs. `max_reward_qty` is a hard on/off boundary,
  not a partial discount: at qty <= max_reward_qty every unit on the line
  is discounted; at qty > max_reward_qty the line is completely plain - no
  banner, no "Max:" indicator, nothing (confirmed at qty=3 against
  max_reward_qty=2). This differs from a Basic promo's "Range:" line,
  which stays visible even when the current qty is out of range.

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
from utilities.promotion_asserts import assert_promo_state

logger = get_logger(__name__)

with open("data/test_data.yaml", "r", encoding="utf-8") as f:
    TEST_DATA = yaml.safe_load(f)

CFG = TEST_DATA["promotion_sale"]


@allure.suite("Marketing Promotions")
@allure.feature("Promotions")
@allure.story("Buy 3 get 2 (different product) at 50% off - plus the reward max-qty boundary")
@pytest.mark.promotion
@pytest.mark.e2e
class TestPromotionBuy3Get2(MobileBaseSetup):

    # ---- shared context ----
    scenario = None
    customer_name = None
    trigger_sku = None
    trigger_upc = None
    reward_sku = None
    reward_upc = None
    promo_name = None
    trigger_qty = None
    max_reward_qty = None
    reward_percent = None

    trigger_base_price = None
    reward_base_price = None
    reward_expected_discounted_price = None
    grand_total = None
    order_no = None

    sales_history = None
    cso = None
    cart_summary = None
    payment = None

    # ---------------------------------------------------------------- #
    @allure.title("Load the buy3_get2_half_off scenario and resolve both products' SKUs")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_01_load_scenario_data(self):
        with allure.step("Read testdata/mobile_promotion_scenarios_<env>.json ('buy3_get2_half_off')"):
            scenario = promotion_data.get_scenario("buy3_get2_half_off", env=CFG["env"])
            TestPromotionBuy3Get2.scenario = scenario
            params = scenario["params"]
            TestPromotionBuy3Get2.customer_name = scenario["customer"]
            TestPromotionBuy3Get2.trigger_upc = scenario["trigger_product"]["piece_upc"]
            TestPromotionBuy3Get2.reward_upc = scenario["reward_product"]["piece_upc"]
            TestPromotionBuy3Get2.promo_name = scenario["promotion"]["name"]
            TestPromotionBuy3Get2.trigger_qty = params["trigger_qty"]
            TestPromotionBuy3Get2.max_reward_qty = params["max_reward_qty"]
            TestPromotionBuy3Get2.reward_percent = params["reward_percent"]
        with allure.step("Resolve both products' SKUs by UPC"):
            client = ApiClient()
            trig = client.get_product_by_upc(self.trigger_upc)
            rew = client.get_product_by_upc(self.reward_upc)
            assert trig and rew, f"Trigger/reward product lookup failed: trig={trig} rew={rew}"
            TestPromotionBuy3Get2.trigger_sku = trig["sku"]
            TestPromotionBuy3Get2.reward_sku = rew["sku"]
            logger.info(f"Buy3Get2 '{self.promo_name}': buy {self.trigger_qty} of trigger SKU="
                        f"{self.trigger_sku} -> up to {self.max_reward_qty} units of reward SKU="
                        f"{self.reward_sku} at {self.reward_percent}% off")

    # -------------- helper (not a test) -------------- #
    def _open_fresh_order_to_product_step(self):
        sh = self.dashboard.go_to_sales_history()
        assert sh.is_loaded(), "Sales History did not open"
        cso = sh.tap_create_sale_order()
        assert cso.is_loaded(), "Create Sale Order page did not open"
        cso.select_customer(self.customer_name)
        assert cso.is_customer_selected(self.customer_name), f"Customer {self.customer_name} not selected"
        cso.set_order_type(CFG["order_type"])
        cso.set_internal_note(f"{CFG['internal_note_prefix']}-buy3get2")
        cso.set_invoice_note(f"{CFG['invoice_note_prefix']}-buy3get2")
        cso.tap_next()
        assert cso.is_product_step_loaded(), "Did not reach the product-selection step"
        return cso

    # ---------------- Part 1: reward qty ABOVE max_reward_qty - no discount at all #
    @allure.title("Boundary: reward qty > max_reward_qty gets NO discount, even with trigger met")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_02_boundary_reward_qty_exceeds_max_no_discount(self):
        over_qty = self.max_reward_qty + 1
        with allure.step(f"Fresh order: reward at qty={over_qty} (> max_reward_qty={self.max_reward_qty})"):
            cso = self._open_fresh_order_to_product_step()
            cso.add_product_by_sku(self.reward_sku, qty=over_qty, upc=self.reward_upc)
            line = cso.get_cart_line(self.reward_sku, upc=self.reward_upc)
            assert_promo_state(line, False, "Reward discounted before any trigger in cart - ")
        with allure.step(f"Add trigger at qty={self.trigger_qty} (meets trigger_qty) - reward STILL plain"):
            cso.add_product_by_sku(self.trigger_sku, qty=self.trigger_qty, upc=self.trigger_upc)
            line = cso.get_cart_line(self.reward_sku, upc=self.reward_upc)
            assert_promo_state(line, False, (
                f"Reward discounted despite qty={over_qty} exceeding max_reward_qty="
                f"{self.max_reward_qty} - "))
            assert money(line["sub_total"]) == money(line["line_total"]), (
                f"Over-max reward line should be full price: Sub Total {line.get('sub_total')} "
                f"!= Total {line.get('line_total')}")
            TestPromotionBuy3Get2.reward_base_price = money(line["sale_price"])
        with allure.step("Discard this throwaway order"):
            TestPromotionBuy3Get2.sales_history = cso.discard_order()

    # ---------------- Part 2: the real order - reward added first, plain -- #
    @allure.title("Add the reward product (at exactly max_reward_qty) first - plain, no trigger yet")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_03_add_reward_at_max_qty_before_trigger(self):
        with allure.step(f"Fresh order (kept): reward at qty={self.max_reward_qty} (== max_reward_qty)"):
            cso = self._open_fresh_order_to_product_step()
            cso.add_product_by_sku(self.reward_sku, qty=self.max_reward_qty, upc=self.reward_upc)
            TestPromotionBuy3Get2.cso = cso
        with allure.step("Line is plain - no trigger in cart yet"):
            line = cso.get_cart_line(self.reward_sku, upc=self.reward_upc)
            assert_promo_state(line, False, "Reward already discounted with no trigger in cart - ")
            assert money(line["sub_total"]) == money(line["line_total"])

    # ---------------- Part 3: trigger below threshold - no change --------- #
    @allure.title("Add the trigger product below trigger_qty - reward still undiscounted")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_04_add_trigger_below_threshold_no_discount_yet(self):
        below_qty = self.trigger_qty - 1
        assert below_qty >= 1, f"trigger_qty {self.trigger_qty} leaves no below-threshold qty to test"
        with allure.step(f"Add trigger at qty={below_qty} (< trigger_qty={self.trigger_qty})"):
            self.cso.add_product_by_sku(self.trigger_sku, qty=below_qty, upc=self.trigger_upc)
        with allure.step("Reward line is still plain/undiscounted"):
            line = self.cso.get_cart_line(self.reward_sku, upc=self.reward_upc)
            assert_promo_state(line, False, (
                f"Reward discounted before trigger_qty ({self.trigger_qty}) was met "
                f"(trigger qty={below_qty}) - "))

    # ---------------- Part 4: trigger meets threshold - reward fully discounts #
    @allure.title("Push the trigger to meet trigger_qty - reward's full qty discounts at 50%")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_05_trigger_meets_threshold_reward_fully_discounts(self):
        with allure.step("Add 1 more of the SAME trigger product - merges into one line, reaches trigger_qty"):
            self.cso.add_product_by_sku(self.trigger_sku, qty=1, upc=self.trigger_upc)
        with allure.step(f"Trigger line: qty={self.trigger_qty}, itself NOT discounted"):
            trig_line = self.cso.get_cart_line(self.trigger_sku, upc=self.trigger_upc)
            assert_promo_state(trig_line, False,
                "Trigger line itself should never be discounted (skip_discounted_trigger) - ")
            assert trig_line.get("promo_name") == self.promo_name, (
                f"Trigger line promo name {trig_line.get('promo_name')!r} != {self.promo_name!r}")
            assert trig_line.get("promo_trigger_qty") == self.trigger_qty, (
                f"Trigger line's displayed Min != {self.trigger_qty}: {trig_line}")
            assert money(trig_line["sub_total"]) == money(trig_line["line_total"]), (
                f"Trigger line should be full price: Sub Total {trig_line.get('sub_total')} != "
                f"Total {trig_line.get('line_total')}")
            TestPromotionBuy3Get2.trigger_base_price = money(trig_line["sale_price"])

        with allure.step(f"Reward line: ALL {self.max_reward_qty} units now discounted {self.reward_percent}% off"):
            rew_line = self.cso.get_cart_line(self.reward_sku, upc=self.reward_upc)
            assert_promo_state(rew_line, True, "Reward line did not discount once trigger_qty was met - ")
            assert rew_line["promo_name"] == self.promo_name, (
                f"Reward line promo name {rew_line.get('promo_name')!r} != {self.promo_name!r}")
            assert rew_line["promo_percent"] == self.reward_percent, (
                f"Reward line discount {rew_line.get('promo_percent')}% != {self.reward_percent}%")
            assert rew_line.get("promo_max_reward_qty") == self.max_reward_qty, (
                f"Reward line's displayed Max != {self.max_reward_qty}: {rew_line}")
            expected_discounted = money(
                self.reward_base_price * (Decimal(100) - self.reward_percent) / Decimal(100))
            TestPromotionBuy3Get2.reward_expected_discounted_price = expected_discounted
            assert money(rew_line["promo_discounted_price"]) == expected_discounted, (
                f"Reward discounted price {rew_line.get('promo_discounted_price')} != {expected_discounted}")
            expected_sub_total = money(self.reward_base_price * self.max_reward_qty)
            expected_line_total = money(expected_discounted * self.max_reward_qty)
            assert money(rew_line["sub_total"]) == expected_sub_total, (
                f"Reward Sub Total {rew_line.get('sub_total')} != {expected_sub_total}")
            assert money(rew_line["line_total"]) == expected_line_total, (
                f"Reward Total {rew_line.get('line_total')} != {expected_line_total} "
                f"(ALL {self.max_reward_qty} units discounted, not just some)")
            allure.attach(f"trigger: {trig_line}\nreward: {rew_line}",
                           name="Trigger + reward lines (Buy3Get2)", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Next -> Cart Summary"):
            TestPromotionBuy3Get2.cart_summary = self.cso.tap_next_to_summary()

    # ---------------- Part 5: validate the cart summary ------------------- #
    @allure.title("Validate Cart Summary: discount covers exactly max_reward_qty reward units")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_06_validate_cart_summary(self):
        cs = self.cart_summary
        trigger_full_total = money(self.trigger_base_price * self.trigger_qty)
        reward_discounted_total = money(self.reward_expected_discounted_price * self.max_reward_qty)
        expected_total = money(trigger_full_total + reward_discounted_total)
        with allure.step("Total quantity (trigger + reward), discounted Sub Total, Promo Savings, Grand Total"):
            cs.scroll_to_summary()
            assert cs.get_total_quantity() == self.trigger_qty + self.max_reward_qty, (
                f"Total Quantity != {self.trigger_qty} (trigger) + {self.max_reward_qty} (reward)")
            assert money(cs.get_sub_total()) == expected_total, (
                f"Cart Summary Sub Total {cs.get_sub_total()} != {expected_total}")
            reward_full_total = money(self.reward_base_price * self.max_reward_qty)
            expected_savings = reward_full_total - reward_discounted_total
            promo_savings = money(abs(cs.get_promo_savings()))
            assert promo_savings == money(expected_savings), (
                f"Promo Savings {promo_savings} != expected {expected_savings} "
                f"(only the {self.max_reward_qty} reward units are discounted, by {self.reward_percent}%)")
            tax = money(cs.get_tax())
            TestPromotionBuy3Get2.grand_total = money(cs.get_grand_total())
            assert self.grand_total == money(expected_total + tax), (
                f"Grand Total {self.grand_total} != {expected_total} + tax {tax}")
        with allure.step("Proceed to Checkout"):
            TestPromotionBuy3Get2.payment = cs.proceed_to_checkout()

    # ---------------- Part 6: complete the sale with cash ------------------ #
    @allure.title("Pay in full with Cash and complete the sale")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_07_complete_cash_sale(self):
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
            TestPromotionBuy3Get2.sales_history = pay.tap_ok_return_to_sales_history()

    # ---------------- Part 7: validate in Sales History --------------------#
    @allure.title("Validate the new order in Sales History and capture its number")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_08_validate_sales_history(self):
        sh = self.sales_history
        with allure.step("Locate the newest card for this customer, capture Order Number"):
            order_no = sh.capture_latest_order_no(self.customer_name)
            assert order_no.startswith("SO-"), f"Order number {order_no!r} not in SO- format"
            TestPromotionBuy3Get2.order_no = order_no
        with allure.step("Card: customer / Online / Paid / Sale Total == Grand Total"):
            card = sh.get_order_card(order_no)
            assert card.get("Business Name", "").strip() == self.customer_name, "Business Name mismatch"
            assert card.get("Order Type") == "Online", f"Order Type = {card.get('Order Type')!r}"
            assert card.get("Invoice Status") == "Paid", f"Invoice Status = {card.get('Invoice Status')!r}"
            assert money(parse_currency(card.get("Sale Total", "0"))) == self.grand_total, (
                f"Sale Total {card.get('Sale Total')} != Grand Total {self.grand_total}")

    @allure.title("Validate via View Details - order-level totals")
    @allure.severity(allure.severity_level.NORMAL)
    def test_09_validate_view_details(self):
        # Order-level totals only - View Details' own per-line "Extended"
        # field is known to miscompute a discounted line (confirmed live in
        # test_promotion_multi_tier.py), so the reward line's Extended is
        # not asserted on here either.
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
            TestPromotionBuy3Get2.sales_history = details.go_back()
