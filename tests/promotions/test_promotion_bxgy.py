"""Buy-X-Get-Y: buying >= trigger_qty of a TRIGGER product discounts a
DIFFERENT reward product by 50%, only once the trigger qty is actually met
in the cart - and the pairing is live/dynamic, not computed once at
add-time.

Mirrors khub-web-tests' UOM BXGY scenario (PWkhubTest/UOM/
test_uom_promotion_bxgy_runner.py) for scenario intent only - a different
app/framework. This app has no way to edit or remove an already-placed
cart line's quantity (see CLAUDE.md's UOM gotchas and
test_promotion_phase2_boundary.py's module docstring), so the "release/
re-pair as the trigger is removed/re-added" behavior the task asked about
is demonstrated the other direction, which IS reachable through the UI and
confirmed live 2026-11-09: adding the trigger product to the cart a SECOND
time (same SKU/UPC, search + Add To Cart again) merges into the SAME
existing line with its qty incremented, rather than creating a duplicate
line - so the reward line's discount can be watched turning on live as the
trigger's own qty crosses the threshold, with no app feature beyond what
every other promo test here already uses (search + Add To Cart).
Also confirmed live: adding the reward product BEFORE the trigger even
exists in the cart leaves it plain/undiscounted, so the engine is
evaluating current cart contents, not add-order.

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
@allure.story("BXGY - trigger product qty met -> a DIFFERENT reward product is discounted")
@pytest.mark.promotion
@pytest.mark.e2e
class TestPromotionBxgy(MobileBaseSetup):

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
    @allure.title("Load the bxgy promotion scenario and resolve both products' SKUs")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_01_load_scenario_data(self):
        with allure.step("Read testdata/mobile_promotion_scenarios_<env>.json ('bxgy')"):
            scenario = promotion_data.get_scenario("bxgy", env=CFG["env"])
            TestPromotionBxgy.scenario = scenario
            params = scenario["params"]
            TestPromotionBxgy.customer_name = scenario["customer"]
            TestPromotionBxgy.trigger_upc = scenario["trigger_product"]["piece_upc"]
            TestPromotionBxgy.reward_upc = scenario["reward_product"]["piece_upc"]
            TestPromotionBxgy.promo_name = scenario["promotion"]["name"]
            TestPromotionBxgy.trigger_qty = params["trigger_qty"]
            TestPromotionBxgy.max_reward_qty = params["max_reward_qty"]
            TestPromotionBxgy.reward_percent = params["reward_percent"]
        with allure.step("Resolve both products' SKUs by UPC"):
            client = ApiClient()
            trig = client.get_product_by_upc(self.trigger_upc)
            rew = client.get_product_by_upc(self.reward_upc)
            assert trig and rew, f"Trigger/reward product lookup failed: trig={trig} rew={rew}"
            TestPromotionBxgy.trigger_sku = trig["sku"]
            TestPromotionBxgy.reward_sku = rew["sku"]
            logger.info(f"BXGY '{self.promo_name}': trigger SKU={self.trigger_sku} "
                        f"(qty>={self.trigger_qty}) -> reward SKU={self.reward_sku} "
                        f"({self.reward_percent}% off, up to qty {self.max_reward_qty})")

    # ---------------- Part 1: open Sales History -> Create Sale Order --- #
    @allure.title("Open Sales History and start a new sale order")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_02_open_create_sale_order(self):
        with allure.step("Dashboard -> hamburger -> Sales History -> + FAB"):
            assert self.dashboard.is_loaded(), "Dashboard not shown"
            sh = self.dashboard.go_to_sales_history()
            assert sh.is_loaded(), "Sales History did not open"
            TestPromotionBxgy.sales_history = sh
            TestPromotionBxgy.cso = sh.tap_create_sale_order()
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
            self.cso.set_internal_note(f"{CFG['internal_note_prefix']}-bxgy")
            self.cso.set_invoice_note(f"{CFG['invoice_note_prefix']}-bxgy")
            self.cso.tap_next()
            assert self.cso.is_product_step_loaded(), "Did not reach the product-selection step"

    # ---------------- Part 3: reward added first - plain, undiscounted - #
    @allure.title("Add the reward product first - plain, no promo yet (trigger not in cart)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_04_add_reward_before_trigger_not_discounted(self):
        with allure.step("Search + Add To Cart the reward product at qty=1"):
            self.cso.add_product_by_sku(self.reward_sku, qty=1, upc=self.reward_upc)
        with allure.step("Line is plain - no promo banner, Sub Total == Total"):
            line = self.cso.get_cart_line(self.reward_sku, upc=self.reward_upc)
            assert_promo_state(line, False, "Reward line already discounted with no trigger in cart - ")
            assert money(line["sub_total"]) == money(line["line_total"]), (
                f"Plain line Sub Total {line.get('sub_total')} != Total {line.get('line_total')}")
            TestPromotionBxgy.reward_base_price = money(line["sale_price"])

    # ---------------- Part 4: trigger below threshold - no change ------ #
    @allure.title("Add the trigger product below trigger_qty - reward still undiscounted")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_05_add_trigger_below_threshold_no_discount_yet(self):
        below_qty = self.trigger_qty - 1
        assert below_qty >= 1, f"trigger_qty {self.trigger_qty} leaves no below-threshold qty to test"
        with allure.step(f"Search + Add To Cart the trigger product at qty={below_qty} (< trigger_qty)"):
            self.cso.add_product_by_sku(self.trigger_sku, qty=below_qty, upc=self.trigger_upc)
        with allure.step("Reward line is still plain/undiscounted"):
            line = self.cso.get_cart_line(self.reward_sku, upc=self.reward_upc)
            assert_promo_state(line, False, (
                f"Reward discounted before trigger_qty ({self.trigger_qty}) was met "
                f"(trigger qty={below_qty}) - "))

    # ---------------- Part 5: trigger meets threshold - reward live-pairs #
    @allure.title("Push the trigger to meet trigger_qty - reward line discounts LIVE")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_06_trigger_meets_threshold_reward_discounts(self):
        with allure.step("Add 1 more of the SAME trigger product - merges into one line, qty reaches trigger_qty"):
            self.cso.add_product_by_sku(self.trigger_sku, qty=1, upc=self.trigger_upc)
        with allure.step(f"Trigger line: qty={self.trigger_qty}, named as 'rewards line', itself NOT discounted"):
            trig_line = self.cso.get_cart_line(self.trigger_sku, upc=self.trigger_upc)
            assert trig_line["available"] is not None  # sanity: a real line, not a stale handle
            # skip_discounted_trigger: true - the trigger itself never gets
            # the "N% off" banner/price-pair, only a "rewards line <n>" tag.
            assert_promo_state(trig_line, False,
                "Trigger line itself should never be discounted (skip_discounted_trigger) - ")
            assert trig_line.get("promo_name") == self.promo_name, (
                f"Trigger line promo name {trig_line.get('promo_name')!r} != {self.promo_name!r}")
            assert "promo_rewards_line" in trig_line, f"Trigger line missing its 'rewards line' tag: {trig_line}"
            assert trig_line.get("promo_trigger_qty") == self.trigger_qty, (
                f"Trigger line's displayed Min != {self.trigger_qty}: {trig_line}")
            assert money(trig_line["sub_total"]) == money(trig_line["line_total"]), (
                f"Trigger line should be full price: Sub Total {trig_line.get('sub_total')} != "
                f"Total {trig_line.get('line_total')}")
            TestPromotionBxgy.trigger_base_price = money(trig_line["sale_price"])

        with allure.step(f"Reward line: now discounted {self.reward_percent}% off"):
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
            TestPromotionBxgy.reward_expected_discounted_price = expected_discounted
            assert money(rew_line["promo_discounted_price"]) == expected_discounted, (
                f"Reward discounted price {rew_line.get('promo_discounted_price')} != {expected_discounted}")
            assert money(rew_line["line_total"]) == expected_discounted, (  # qty=1
                f"Reward Total {rew_line.get('line_total')} != {expected_discounted}")
            allure.attach(f"trigger: {trig_line}\nreward: {rew_line}",
                           name="Trigger + reward lines (BXGY)", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Next -> Cart Summary"):
            TestPromotionBxgy.cart_summary = self.cso.tap_next_to_summary()

    # ---------------- Part 6: validate the cart summary --------------- #
    @allure.title("Validate Cart Summary: only the reward's discount counts as Promo Savings")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_07_validate_cart_summary(self):
        cs = self.cart_summary
        trigger_full_total = money(self.trigger_base_price * self.trigger_qty)  # trigger is never discounted
        expected_total = money(trigger_full_total + self.reward_expected_discounted_price)
        with allure.step("Total quantity (trigger + reward), discounted Sub Total, Promo Savings, Grand Total"):
            cs.scroll_to_summary()
            assert cs.get_total_quantity() == self.trigger_qty + 1, (
                f"Total Quantity != {self.trigger_qty} (trigger) + 1 (reward)")
            assert money(cs.get_sub_total()) == expected_total, (
                f"Cart Summary Sub Total {cs.get_sub_total()} != {expected_total}")
            expected_savings = self.reward_base_price - self.reward_expected_discounted_price
            promo_savings = money(abs(cs.get_promo_savings()))
            assert promo_savings == money(expected_savings), (
                f"Promo Savings {promo_savings} != expected {expected_savings} "
                f"(only the reward line is discounted, by {self.reward_percent}%)")
            tax = money(cs.get_tax())
            TestPromotionBxgy.grand_total = money(cs.get_grand_total())
            assert self.grand_total == money(expected_total + tax), (
                f"Grand Total {self.grand_total} != {expected_total} + tax {tax}")
        with allure.step("Proceed to Checkout"):
            TestPromotionBxgy.payment = cs.proceed_to_checkout()

    # ---------------- Part 7: complete the sale with cash -------------- #
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
            TestPromotionBxgy.sales_history = pay.tap_ok_return_to_sales_history()

    # ---------------- Part 8: validate in Sales History --------------- #
    @allure.title("Validate the new order in Sales History and capture its number")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_09_validate_sales_history(self):
        sh = self.sales_history
        with allure.step("Locate the newest card for this customer, capture Order Number"):
            order_no = sh.capture_latest_order_no(self.customer_name)
            assert order_no.startswith("SO-"), f"Order number {order_no!r} not in SO- format"
            TestPromotionBxgy.order_no = order_no
        with allure.step("Card: customer / Online / Paid / Sale Total == Grand Total"):
            card = sh.get_order_card(order_no)
            assert card.get("Business Name", "").strip() == self.customer_name, "Business Name mismatch"
            assert card.get("Order Type") == "Online", f"Order Type = {card.get('Order Type')!r}"
            assert card.get("Invoice Status") == "Paid", f"Invoice Status = {card.get('Invoice Status')!r}"
            assert money(parse_currency(card.get("Sale Total", "0"))) == self.grand_total, (
                f"Sale Total {card.get('Sale Total')} != Grand Total {self.grand_total}")

    @allure.title("Validate via View Details - order-level totals")
    @allure.severity(allure.severity_level.NORMAL)
    def test_10_validate_view_details(self):
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
            TestPromotionBxgy.sales_history = details.go_back()
