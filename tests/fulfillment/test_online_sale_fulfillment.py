"""End-to-end: create a fully-paid Online sale in the Khub Admin app, validate
it in Sales History, then assign -> pick -> pack it and confirm the same order
lands in the Packed section.

Test data (one customer + 5 products with unique timestamped names, SKUs,
prices) is created through the backend API - never the UI, never hard-coded -
mirroring khub-pos-tests' ApiClient approach. Every product/SKU/quantity/
monetary value and the captured order number are held on the class and
re-validated at each stage.

Structure follows the POS suite (test_split_payment.py): one pytest method per
logical UI step, sharing state via CLASS attributes; conftest.py skips the rest
of the class after any step fails.
"""
from decimal import Decimal

import allure
import pytest
import yaml

from tests.mobile_base_setup import MobileBaseSetup
from utilities.api_client import ApiClient
from utilities.currency import money, parse_currency
from utilities.logger import get_logger

logger = get_logger(__name__)

with open("data/test_data.yaml", "r", encoding="utf-8") as f:
    TEST_DATA = yaml.safe_load(f)

CFG = TEST_DATA["online_sale"]


@allure.feature("Sale Order + Fulfillment")
@allure.story("Paid Online sale -> Sales History -> Assign -> Pick -> Pack -> Packed")
# Category markers only. Suite membership (smoke / regression) is driven by
# data/test_data.xlsx's Tags sheet, not hardcoded here - see conftest.py.
@pytest.mark.fulfillment
@pytest.mark.e2e
class TestOnlineSaleFulfillment(MobileBaseSetup):

    # ---- shared context (populated as the scenario runs) ----
    ctx = {}
    customer = None
    products = None            # [{id,name,sku,upc,price,qty,line_subtotal}]
    expected_subtotal = None   # Decimal
    grand_total = None         # Decimal - captured live from Cart Summary
    tax = None                 # Decimal - captured live
    order_no = None
    logged_in_user = TEST_DATA["login"]["valid"]["username"]

    sales_history = None
    cso = None
    cart_summary = None
    payment = None
    fulfillment = None
    picking = None

    # ---------------------------------------------------------------- #
    @allure.title("Prepare test data via API (1 customer + products)")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_01_prepare_test_data(self):
        with allure.step("Create customer + products through the backend API"):
            client = ApiClient()
            data = client.create_online_sale_test_data(
                prices=CFG["product_prices"],
                quantities=CFG["quantities"],
                count=CFG["product_count"],
            )
            TestOnlineSaleFulfillment.customer = data["customer"]
            TestOnlineSaleFulfillment.products = data["products"]
            TestOnlineSaleFulfillment.expected_subtotal = money(data["expected_subtotal"])

            for p in self.products:
                assert p["sku"], f"Product {p['name']} has no SKU"
                assert p["qty"] >= 1
                assert "QA-" in p["name"], f"Product name not tagged unique: {p['name']!r}"
                logger.info(f"  {p['name']}  SKU={p['sku']}  ${p['price']} x {p['qty']} = ${p['line_subtotal']}")
            assert "QA-" in self.customer["name"], \
                f"Customer name not tagged unique: {self.customer['name']!r}"
            names_seen = [p["name"] for p in self.products]
            assert len(set(names_seen)) == len(names_seen), f"Product names not unique: {names_seen}"
            assert len(self.products) == CFG["product_count"]
            logger.info(f"Customer: {self.customer['name']} (id={self.customer['id']})")
            logger.info(f"Expected subtotal: ${self.expected_subtotal}")
            allure.attach(
                "\n".join(f"{p['sku']}  {p['name']}  ${p['price']} x{p['qty']}" for p in self.products),
                name="Generated products", attachment_type=allure.attachment_type.TEXT)

    # ---------------- Part 1: open Sales History -> Create Sale Order --- #
    @allure.title("Open Sales History and start a new sale order")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_02_open_create_sale_order(self):
        with allure.step("Dashboard -> hamburger -> Sales History -> + FAB"):
            assert self.dashboard.is_loaded(), "Dashboard not shown"
            sh = self.dashboard.go_to_sales_history()
            assert sh.is_loaded(), "Sales History did not open"
            TestOnlineSaleFulfillment.sales_history = sh
            TestOnlineSaleFulfillment.cso = sh.tap_create_sale_order()
            assert self.cso.is_loaded(), "Create Sale Order page did not open"

    # ---------------- Part 2: customer + order info -------------------- #
    @allure.title("Add customer and order information")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_03_customer_and_order_info(self):
        name = self.customer["name"]
        with allure.step(f"Select API customer '{name}' and verify it is applied"):
            self.cso.select_customer(name)
            assert self.cso.is_customer_selected(name), f"Customer {name} not selected"
            fields = self.cso.get_selected_customer_fields()
            assert name in fields, "Selected customer card does not show the generated name"
            assert self.customer["email"] in fields, "Selected customer card email mismatch"
            if self.customer.get("no"):
                assert str(self.customer["no"]) in fields, "Customer No mismatch on the selected card"
        with allure.step("Order Type = Online, add unique internal + invoice notes, Next"):
            self.cso.set_order_type(CFG["order_type"])
            TestOnlineSaleFulfillment.ctx["internal_note"] = f"{CFG['internal_note_prefix']}-{self.customer['id']}"
            TestOnlineSaleFulfillment.ctx["invoice_note"] = f"{CFG['invoice_note_prefix']}-{self.customer['id']}"
            self.cso.set_internal_note(self.ctx["internal_note"])
            self.cso.set_invoice_note(self.ctx["invoice_note"])
            self.cso.tap_next()
            assert self.cso.is_product_step_loaded(), "Did not reach the product-selection step"

    # ---------------- Part 3: add the products ------------------------ #
    @allure.title("Add every generated product by SKU and validate line subtotals")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_04_add_products(self):
        for p in self.products:
            with allure.step(f"Add SKU {p['sku']} (qty {p['qty']})"):
                self.cso.add_product_by_sku(p["sku"], qty=p["qty"])
        with allure.step("Every product is in the cart and each subtotal == price x qty"):
            for p in self.products:
                assert self.cso.is_in_cart(p["sku"]), f"SKU {p['sku']} missing from cart"
                line = self.cso.get_cart_line(p["sku"])
                expected = money(Decimal(str(p["price"])) * p["qty"])
                assert money(line["sub_total"]) == expected, (
                    f"SKU {p['sku']} subtotal {line['sub_total']} != {expected}")
                p["ui_sub_total"] = float(expected)
        with allure.step("Next -> Cart Summary"):
            TestOnlineSaleFulfillment.cart_summary = self.cso.tap_next_to_summary()

    # ---------------- Part 4: validate the cart summary --------------- #
    @allure.title("Validate the Cart Summary totals")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_05_validate_cart_summary(self):
        cs = self.cart_summary
        with allure.step("Distinct products, total quantity, subtotal, discount, tax, grand total"):
            cs.scroll_to_summary()
            assert cs.get_total_products() == len(self.products), "Total Products mismatch"
            assert cs.get_total_quantity() == sum(p["qty"] for p in self.products), "Total Quantity mismatch"
            assert money(cs.get_sub_total()) == self.expected_subtotal, "Sub Total mismatch"
            assert money(cs.get_additional_discount()) == money(0), "Additional Discount is not $0.00"

            TestOnlineSaleFulfillment.tax = money(cs.get_tax())
            TestOnlineSaleFulfillment.grand_total = money(cs.get_grand_total())
            expected_grand = money(self.expected_subtotal + self.tax)
            assert self.grand_total == expected_grand, (
                f"Grand Total {self.grand_total} != subtotal {self.expected_subtotal} + tax {self.tax}")
            logger.info(f"Captured Grand Total = ${self.grand_total} (tax ${self.tax})")
        with allure.step("Proceed to Checkout"):
            TestOnlineSaleFulfillment.payment = cs.proceed_to_checkout()

    # ---------------- Part 5: complete the sale with cash ------------- #
    @allure.title("Pay in full with Cash and complete the sale")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_06_complete_cash_sale(self):
        pay = self.payment
        with allure.step("Invoice Total == Grand Total; correct customer"):
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
            TestOnlineSaleFulfillment.sales_history = pay.tap_ok_return_to_sales_history()

    # ---------------- Part 6: validate in Sales History -------------- #
    @allure.title("Validate the new order in Sales History and capture its number")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_07_validate_sales_history(self):
        sh = self.sales_history
        with allure.step("Locate the newest card for the generated customer, capture Order Number"):
            order_no = sh.capture_latest_order_no(self.customer["name"])
            assert order_no.startswith("SO-"), f"Order number {order_no!r} not in SO- format"
            TestOnlineSaleFulfillment.order_no = order_no
            allure.attach(order_no, name="Order Number", attachment_type=allure.attachment_type.TEXT)
        with allure.step("Card fields: customer / Online / Paid / Pending / Sale Total == Grand Total"):
            card = sh.get_order_card(order_no)
            assert card.get("Business Name", "").strip() == self.customer["name"], "Business Name mismatch"
            assert card.get("Order Type") == "Online", f"Order Type = {card.get('Order Type')!r}"
            assert card.get("Invoice Status") == "Paid", f"Invoice Status = {card.get('Invoice Status')!r}"
            assert card.get("Status") == "Pending", f"Status = {card.get('Status')!r}"
            assert money(parse_currency(card.get("Sale Total", "0"))) == self.grand_total, (
                f"Sale Total {card.get('Sale Total')} != Grand Total {self.grand_total}")

    @allure.title("Validate the order via View Details")
    @allure.severity(allure.severity_level.NORMAL)
    def test_08_validate_view_details(self):
        sh = self.sales_history
        with allure.step("Actions -> View Details, check order number / customer / totals / products"):
            details = sh.open_order_details(self.order_no)
            assert details.is_shown(), "Order Details did not open"
            ok, missing = details.contains_all(
                self.order_no,
                self.customer["name"],
                f"{self.grand_total:.2f}",
            )
            assert ok, f"Order Details missing expected values: {missing}"
            # each product name should appear
            blob = details.read_all_text()
            for p in self.products:
                assert p["name"] in blob or p["sku"] in blob, f"Product {p['sku']} not in Order Details"
            sh = details.go_back()
            TestOnlineSaleFulfillment.sales_history = sh

    # ---------------- Part 7: Fulfillment -> assign ------------------ #
    @allure.title("Open Fulfillment and assign the order to me")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_09_assign_order(self):
        with allure.step("Dashboard -> Fulfillment -> Pending -> locate the exact order"):
            ful = self.dashboard.go_to_fulfillment()
            assert ful.is_loaded(), "Fulfillment page did not open"
            ful.open_pending()
            ful.search(self.order_no)
            assert ful.is_order_present(self.order_no), f"Order {self.order_no} not in Pending"
            TestOnlineSaleFulfillment.fulfillment = ful
        with allure.step("Open order -> Assign to me -> confirmation names the logged-in user"):
            msg = ful.assign_order_to_me(self.order_no)
            logger.info(f"Assign message: {msg!r}")
            assert "assign" in msg.lower(), f"Unexpected assign message: {msg!r}"
            assert self.logged_in_user in msg, "Assign message does not name the logged-in user"
        with allure.step("The order now shows the logged-in user as picker"):
            assert ful.is_assigned_to(self.order_no, self.logged_in_user), \
                "Order is not shown as assigned to the logged-in user"

    # ---------------- Part 8: pick ---------------------------------- #
    @allure.title("Pick all products")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_10_pick_products(self):
        ful = self.fulfillment
        with allure.step("Re-open the order by number -> Start Picking"):
            ful.search(self.order_no)
            picking = ful.open_order_for_picking(self.order_no)
            picking.start_picking()
            TestOnlineSaleFulfillment.picking = picking
        with allure.step("Skip Scan Pick All -> Yes -> Pick; workflow advances to packing"):
            picking.skip_scan_pick_all()
            assert picking.is_all_picked(), "Workflow did not advance to the packing stage"

    # ---------------- Part 9: pack --------------------------------- #
    @allure.title("Pack all products")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_11_pack_products(self):
        with allure.step("Start Packing -> Skip Scan Pack All -> Yes -> Pack"):
            packing = self.picking.start_packing()
            assert packing.is_shown(), "Packing Progress page did not open"
            packing.skip_scan_pack_all()
        with allure.step("'successfully packed' dialog names this order -> OK"):
            msg = packing.wait_packed_success()
            assert "successfully packed" in msg.lower(), f"Unexpected packed message: {msg!r}"
            assert self.order_no in msg, f"Packed message does not name {self.order_no}: {msg!r}"

    # ---------------- Part 10: Packed section ---------------------- #
    @allure.title("Confirm the same order appears in the Packed section")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_12_validate_packed_section(self):
        with allure.step("Fulfillment opens; order has left the Pending section"):
            ful = self.dashboard.go_to_fulfillment()
            assert ful.is_loaded(), "Fulfillment did not open"
            still_pending = ful.is_order_in_pending(self.order_no)
            logger.info(f"Order still in Pending after packing: {still_pending}")
            assert not still_pending, "Order still appears under Pending after packing"
        with allure.step("Open the Packed tab and locate the captured order number"):
            ful.open_packed()
            assert ful.is_packed_tab_selected(), "Packed tab is not the active tab"
            ful.search(self.order_no)
            assert ful.is_order_present(self.order_no), (
                f"Order {self.order_no} not found in the Packed section")
        with allure.step("The Packed card is the same order: number / customer / Online / picker"):
            desc = ful.get_order_desc(self.order_no)
            assert self.order_no in desc, "Packed card order number mismatch"
            assert self.customer["name"] in desc, "Packed card shows the wrong customer"
            assert "Online" in desc, "Packed card Order Type is not Online"
            # picker info, when the card exposes it, should be the logged-in user
            if "Picker Detail" in desc:
                assert self.logged_in_user in desc, "Packed card picker is not the logged-in user"
            allure.attach(desc, name="Packed order card", attachment_type=allure.attachment_type.TEXT)
            # leave the run on the Packed tab with the order visible as evidence
            try:
                shot = self.dashboard.take_screenshot("packed_section_final")
                with open(shot, "rb") as fh:
                    allure.attach(fh.read(), name="Packed section (final)",
                                  attachment_type=allure.attachment_type.PNG)
            except Exception as e:
                logger.warning(f"Could not attach final Packed screenshot: {e}")
