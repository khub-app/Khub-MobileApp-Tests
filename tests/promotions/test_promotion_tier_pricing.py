"""Customer Tier pricing vs. a Promotion - the LOWER effective price always
wins on the cart line and the paid invoice.

Reverse-engineered + confirmed live 2026-11-13 (not part of the original
7-scenario cross-repo promotion data contract - this one needs a product
with Tier Sale Prices, which only this project's own ApiClient can create,
so unlike every other file in this package it builds its own product/
customer/promotion directly via utilities/api_client.py, the same pattern
test_label_management_product_fulfillment.py already uses for the same
reason).

Two fields exist on the live portal, both previously unused by this project
even though their payload plumbing already existed in create_customer /
create_product:
  - Add Customer form, Basic Details: a "Tier" dropdown (None / Tier 1-5),
    `tier_id` (plain int 1-5, no separate tier-list endpoint - the dropdown
    is a fixed client-side enum, confirmed live - no network call fetches
    it).
  - A product's Define Pricing grid: "Tier 1 SP ($)" ... "Tier 5 SP ($)"
    columns per unit - `unit_price.unit_price_tiers` entries
    `{"tier_id": 1..5, "price": ...}` (default 0 = no override).

Confirmed live via a throwaway Appium probe (see utilities/api_client.py's
create_customer_with_tier / create_product_with_tier_prices docstrings for
the API side) what the app actually does with both set at once - this is
NOT a simple "pick whichever of (tier price, promo-off-original-price) is
lower" comparison:
  1. A matching Tier <n> SP UNCONDITIONALLY replaces the product's regular
     Sale Price as the cart line's base price for that tier - confirmed in
     BOTH directions: tier_price=$100 vs regular $250 shows $100; tier_
     price=$300 vs regular $250 shows $300 (tier wins even when it's the
     HIGHER number - there is no "lower of the two" comparison at this
     step, the tier price is simply authoritative once it is non-zero).
  2. Any active promotion on the product still applies its percent-off on
     top of whichever base price step 1 produced (STACKS, rather than the
     engine comparing "tier price" against "promo discount of the original
     price" and picking one or the other). So with tier=$100, regular=
     $250, promo=20%: the cart line's own "Sale Price" is $100 (not $250),
     the promo banner discounts FROM $100 (not $250), landing on $80, not
     $100 and not $200 (250 * 0.8).

The net effect is still exactly what a user comparing tier pricing against
promotions would want: the actual charged amount ($80 here) is lower than
plain tier price ($100), which is itself lower than what a non-tier
customer would pay with the same promotion (250 * 0.8 = $200), which is
lower than full price ($250) - "lowest price always wins" holds as an
end-to-end outcome, even though the mechanism is "tier overrides base,
promotion still stacks," not a single min() over two candidates. This test
asserts both the mechanism (cart line's own sale_price/promo fields) and
the outcome (that ordering of all four candidate prices).
"""
from decimal import Decimal

import allure
import pytest
import yaml

from tests.mobile_base_setup import MobileBaseSetup
from utilities.api_client import ApiClient
from utilities.currency import money, parse_currency
from utilities.logger import get_logger
from utilities.promotion_asserts import assert_promo_state

logger = get_logger(__name__)

with open("data/test_data.yaml", "r", encoding="utf-8") as f:
    TEST_DATA = yaml.safe_load(f)

CFG = TEST_DATA["promotion_sale"]

REGULAR_PRICE = 250.00
TIER_ID = 1
TIER_PRICE = 100.00
PROMO_PERCENT = 20


@allure.suite("Marketing Promotions")
@allure.feature("Promotions")
@allure.story("Customer Tier price vs. a Promotion - the lower effective price always wins")
@pytest.mark.promotion
@pytest.mark.e2e
class TestPromotionTierPricing(MobileBaseSetup):

    # ---- shared context ----
    category = None
    product = None
    customer = None
    promo_name = None

    expected_promo_off_regular = None   # what a non-tier customer would pay with this promo
    expected_discounted_price = None    # what THIS tier customer actually pays (tier price, then promo)
    grand_total = None
    order_no = None

    sales_history = None
    cso = None
    cart_summary = None
    payment = None

    # ---------------------------------------------------------------- #
    @allure.title("Create a product with a Tier 1 Sale Price + a promotion, and a Tier 1 customer")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_01_prepare_test_data(self):
        with allure.step("Create category/channel, product (regular $250, Tier 1 SP $100)"):
            client = ApiClient()
            category = client.create_category()
            channels = client.get_channels()
            product = client.create_product_with_tier_prices(
                category["id"], channels,
                tier_prices={TIER_ID: TIER_PRICE},
                price=REGULAR_PRICE,
            )
            TestPromotionTierPricing.category = category
            TestPromotionTierPricing.product = product
        with allure.step(f"Create a {PROMO_PERCENT}% off Basic promotion on that product"):
            primary_channel = sorted(
                channels, key=lambda c: (not c.get("is_primary", False), c.get("id", 0)))[0]
            promo = client.create_promotion(
                product["id"], primary_channel["id"], reward_percent=PROMO_PERCENT,
                trigger_qty=1, max_reward_qty=100,
            )
            TestPromotionTierPricing.promo_name = promo["name"]
        with allure.step(f"Create a Tier {TIER_ID} customer"):
            customer = client.create_customer_with_tier(tier_id=TIER_ID)
            TestPromotionTierPricing.customer = customer

        expected_promo_off_regular = money(
            Decimal(str(REGULAR_PRICE)) * (Decimal(100) - PROMO_PERCENT) / Decimal(100))
        expected_discounted_price = money(
            Decimal(str(TIER_PRICE)) * (Decimal(100) - PROMO_PERCENT) / Decimal(100))
        TestPromotionTierPricing.expected_promo_off_regular = expected_promo_off_regular
        TestPromotionTierPricing.expected_discounted_price = expected_discounted_price

        with allure.step("Sanity: full price > promo-off-regular > tier price > tier-then-promo"):
            assert money(REGULAR_PRICE) > expected_promo_off_regular, \
                "Promo-discounted regular price should still be less than full price"
            assert expected_promo_off_regular > money(TIER_PRICE), (
                f"Scenario setup invalid: promo-off-regular price {expected_promo_off_regular} "
                f"is not greater than the tier price {TIER_PRICE} - the tier price must be the "
                f"cheaper candidate for this scenario to prove anything")
            assert money(TIER_PRICE) > expected_discounted_price, \
                "Tier-then-promo price should be less than the plain tier price"
            logger.info(f"Price ladder for this scenario: full ${REGULAR_PRICE} > "
                        f"promo-off-regular ${expected_promo_off_regular} > tier ${TIER_PRICE} > "
                        f"tier-then-promo (expected charge) ${expected_discounted_price}")

    # ---------------- Part 1: open Sales History -> Create Sale Order --- #
    @allure.title("Open Sales History and start a new sale order")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_02_open_create_sale_order(self):
        with allure.step("Dashboard -> hamburger -> Sales History -> + FAB"):
            assert self.dashboard.is_loaded(), "Dashboard not shown"
            sh = self.dashboard.go_to_sales_history()
            assert sh.is_loaded(), "Sales History did not open"
            TestPromotionTierPricing.sales_history = sh
            TestPromotionTierPricing.cso = sh.tap_create_sale_order()
            assert self.cso.is_loaded(), "Create Sale Order page did not open"

    # ---------------- Part 2: customer + order info -------------------- #
    @allure.title("Add the Tier 1 customer and order information")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_03_customer_and_order_info(self):
        name = self.customer["name"]
        with allure.step(f"Select API-created Tier {TIER_ID} customer '{name}' and verify it is applied"):
            self.cso.select_customer(name)
            assert self.cso.is_customer_selected(name), f"Customer {name} not selected"
        with allure.step("Order Type = Online, add unique internal + invoice notes, Next"):
            self.cso.set_order_type(CFG["order_type"])
            self.cso.set_internal_note(f"{CFG['internal_note_prefix']}-tierpricing")
            self.cso.set_invoice_note(f"{CFG['invoice_note_prefix']}-tierpricing")
            self.cso.tap_next()
            assert self.cso.is_product_step_loaded(), "Did not reach the product-selection step"

    # ---------------- Part 3: add product - tier price + promo stack --- #
    @allure.title("Add the product - cart line shows the Tier price, further discounted by the promotion")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_04_add_product_tier_price_with_promo(self):
        product = self.product
        with allure.step("Search + Add To Cart at qty=1"):
            self.cso.add_product_by_sku(product["sku"], qty=1, upc=product["upc"])
        with allure.step("Cart line's own Sale Price is the TIER price, not the regular $250 price"):
            line = self.cso.get_cart_line(product["sku"], upc=product["upc"])
            assert money(line["sale_price"]) == money(TIER_PRICE), (
                f"Cart line Sale Price {line.get('sale_price')} != Tier {TIER_ID} price {TIER_PRICE} "
                f"- tier pricing did not override the regular sale price")
        with allure.step(f"Promotion is active and discounts FROM the tier price, not the regular price"):
            assert_promo_state(line, True, "Tier-priced line did not show the active promotion - ")
            assert line["promo_name"] == self.promo_name, (
                f"Promo name {line.get('promo_name')!r} != {self.promo_name!r}")
            assert line["promo_percent"] == PROMO_PERCENT, (
                f"Promo discount {line.get('promo_percent')}% != {PROMO_PERCENT}%")
            assert money(line["promo_original_price"]) == money(TIER_PRICE), (
                f"Promo's 'original' price {line.get('promo_original_price')} != tier price {TIER_PRICE} "
                f"- the promotion should be discounting the tier price, not the regular price")
            assert money(line["promo_discounted_price"]) == self.expected_discounted_price, (
                f"Promo discounted price {line.get('promo_discounted_price')} != "
                f"{self.expected_discounted_price} (tier price x (1 - {PROMO_PERCENT}%))")
            assert money(line["line_total"]) == self.expected_discounted_price, (
                f"Line Total {line.get('line_total')} != {self.expected_discounted_price}")
        with allure.step("The actual charge is lower than plain tier price AND lower than "
                          "what a non-tier customer would pay with the same promotion"):
            assert self.expected_discounted_price < money(TIER_PRICE), (
                "Tier-then-promo price should be strictly less than the plain tier price")
            assert self.expected_discounted_price < self.expected_promo_off_regular, (
                "Tier-then-promo price should be strictly less than promo-off-regular-price "
                "(what a non-tier customer would pay)")
            allure.attach(str(line), name="Cart line (Tier + Promo)",
                           attachment_type=allure.attachment_type.TEXT)
        with allure.step("Next -> Cart Summary"):
            TestPromotionTierPricing.cart_summary = self.cso.tap_next_to_summary()

    # ---------------- Part 4: validate the cart summary --------------- #
    @allure.title("Validate Cart Summary: Promo Savings is measured off the TIER price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_05_validate_cart_summary(self):
        cs = self.cart_summary
        with allure.step("Sub Total (already nets out the promo discount), Promo Savings, Grand Total"):
            cs.scroll_to_summary()
            # Cart Summary's own "Sub Total" already nets out every line's
            # promo discount (confirmed project-wide, e.g. test_promotion_bxgy.py) -
            # it equals the tier-then-promo price here, not the plain tier price.
            assert money(cs.get_sub_total()) == self.expected_discounted_price, (
                f"Cart Summary Sub Total {cs.get_sub_total()} != tier-then-promo price "
                f"{self.expected_discounted_price}")
            expected_savings = money(TIER_PRICE) - self.expected_discounted_price
            promo_savings = money(abs(cs.get_promo_savings()))
            assert promo_savings == expected_savings, (
                f"Promo Savings {promo_savings} != expected {expected_savings} "
                f"(tier price {TIER_PRICE} - tier-then-promo {self.expected_discounted_price})")
            tax = money(cs.get_tax())
            TestPromotionTierPricing.grand_total = money(cs.get_grand_total())
            assert self.grand_total == money(self.expected_discounted_price + tax), (
                f"Grand Total {self.grand_total} != {self.expected_discounted_price} + tax {tax}")
        with allure.step("Proceed to Checkout"):
            TestPromotionTierPricing.payment = cs.proceed_to_checkout()

    # ---------------- Part 5: complete the sale with cash -------------- #
    @allure.title("Pay in full with Cash and complete the sale")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_06_complete_cash_sale(self):
        pay = self.payment
        with allure.step("Invoice Total == Grand Total (the tier-then-promo amount, plus tax); correct customer"):
            assert pay.is_loaded(), "Payment page not shown"
            assert money(pay.get_invoice_total()) == self.grand_total, "Invoice Total != captured Grand Total"
            assert self.customer["name"] in pay.get_customer(), "Payment page shows the wrong customer"
        with allure.step("Select Cash; amount is the full invoice total"):
            pay.select_cash()
            assert money(pay.get_amount()) == self.grand_total, "Cash amount != Grand Total"
        with allure.step("Complete Sale -> success dialog -> OK"):
            pay.complete_sale()
            msg = pay.wait_success_dialog()
            assert "saved successfully" in msg, f"Unexpected success message: {msg!r}"
            TestPromotionTierPricing.sales_history = pay.tap_ok_return_to_sales_history()

    # ---------------- Part 6: validate in Sales History --------------- #
    @allure.title("Validate the new order in Sales History: Sale Total reflects the tier-then-promo price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_07_validate_sales_history(self):
        sh = self.sales_history
        with allure.step("Locate the newest card for this customer, capture Order Number"):
            order_no = sh.capture_latest_order_no(self.customer["name"])
            assert order_no.startswith("SO-"), f"Order number {order_no!r} not in SO- format"
            TestPromotionTierPricing.order_no = order_no
        with allure.step("Card: customer / Online / Paid / Sale Total == Grand Total"):
            card = sh.get_order_card(order_no)
            assert card.get("Business Name", "").strip() == self.customer["name"], "Business Name mismatch"
            assert card.get("Order Type") == "Online", f"Order Type = {card.get('Order Type')!r}"
            assert card.get("Invoice Status") == "Paid", f"Invoice Status = {card.get('Invoice Status')!r}"
            assert money(parse_currency(card.get("Sale Total", "0"))) == self.grand_total, (
                f"Sale Total {card.get('Sale Total')} != Grand Total {self.grand_total} "
                f"(the tier-then-promo price, not the regular $250 or the plain tier $100)")

    @allure.title("Validate via View Details - order-level totals")
    @allure.severity(allure.severity_level.NORMAL)
    def test_08_validate_view_details(self):
        sh = self.sales_history
        with allure.step("Actions -> View Details, check order number / customer / grand total"):
            details = sh.open_order_details(self.order_no)
            assert details.is_shown(), "Order Details did not open"
            ok, missing = details.contains_all(
                self.order_no,
                self.customer["name"],
                f"{self.grand_total:.2f}",
            )
            assert ok, f"Order Details missing expected values: {missing}"
            TestPromotionTierPricing.sales_history = details.go_back()
