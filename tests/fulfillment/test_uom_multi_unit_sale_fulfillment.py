"""End-to-end: a UOM product (4 chained packaging tiers - Piece/Pack/Case/
Pallet, custom labels on the top 3) added to a single Online sale as 4
SEPARATE order lines, one per tier, fully paid, validated, then taken through
the same assign -> pick -> pack -> Packed fulfillment lifecycle as
test_online_sale_fulfillment.py.

Mirrors khub-web-tests' UOM multi-unit scenario
(PWkhubTest/UOM/test_uom_multi_unit_sale_fulfilment_validation_runner.py):
one product, 4 tiers, 4 distinct lines, strict per-line price/qty checks
matching what was captured before checkout. The product is created through
the SAME backend API khub-web-tests' scripts/create_uom_products_api.py
uses (ported into utilities/api_client.py's create_uom_product) - never the
UI - so the tier labels/UPCs/prices are read from what the API returns, not
hard-coded.

The Admin app exposes no Unit selector before "Add To Cart" - all 4 tiers
share one SKU and one search result. The only way to add more than one tier
is the cart line's own "Add another unit" menu, which lists just the tiers
not yet in the cart by their configured label (confirmed live 2026-10-29,
see CreateSaleOrderPage.add_product_all_uom_tiers). Every tier line is
therefore addressed by SKU+UPC, not SKU alone - UPC is the only thing that
tells same-SKU tier lines apart (see CreateSaleOrderLocators.cart_line).
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

CFG = TEST_DATA["uom_sale"]


@allure.feature("Sale Order + Fulfillment")
@allure.story("UOM product (4 tiers) -> 4 order lines -> Sales History -> Assign -> Pick -> Pack -> Packed")
@pytest.mark.fulfillment
@pytest.mark.uom
@pytest.mark.e2e
class TestUomMultiUnitSaleFulfillment(MobileBaseSetup):

    # ---- shared context ----
    customer = None
    product = None             # {id,name,sku,piece_upc,pack_upc,case_upc,pallet_upc,
                                #  piece_desc,pack_desc,case_desc,pallet_desc,
                                #  pack_qty,case_qty,pallet_qty,
                                #  piece_price,pack_price,case_price,pallet_price}
    tiers = None                # [{label, upc, price}] x4, Piece/Pack/Case/Pallet order
    expected_subtotal = None    # Decimal
    grand_total = None
    tax = None
    order_no = None
    logged_in_user = TEST_DATA["login"]["valid"]["username"]

    sales_history = None
    cso = None
    cart_summary = None
    payment = None
    fulfillment = None
    picking = None

    # ---------------------------------------------------------------- #
    @allure.title("Prepare test data via API (1 customer + 1 UOM product, 4 tiers)")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_01_prepare_test_data(self):
        with allure.step("Create a UOM product (Piece/Pack/Case/Pallet) + customer through the backend API"):
            client = ApiClient()
            category = client.create_category()
            channels = client.get_channels()
            product = client.create_uom_product(
                category["id"], channels,
                pack_desc=CFG["pack_desc"], case_desc=CFG["case_desc"], pallet_desc=CFG["pallet_desc"],
                pack_qty=CFG["pack_qty"], case_qty=CFG["case_qty"], pallet_qty=CFG["pallet_qty"],
                base_cost=CFG["base_cost"],
            )
            customer = client.create_customer()
            TestUomMultiUnitSaleFulfillment.product = product
            TestUomMultiUnitSaleFulfillment.customer = customer
            TestUomMultiUnitSaleFulfillment.tiers = [
                {"label": "Piece", "upc": product["piece_upc"], "price": product["piece_price"]},
                {"label": product["pack_desc"], "upc": product["pack_upc"], "price": product["pack_price"]},
                {"label": product["case_desc"], "upc": product["case_upc"], "price": product["case_price"]},
                {"label": product["pallet_desc"], "upc": product["pallet_upc"], "price": product["pallet_price"]},
            ]
            upcs_seen = {t["upc"] for t in self.tiers}
            assert len(upcs_seen) == 4, f"Tier UPCs are not all distinct: {self.tiers}"
            assert "QA-" in customer["name"], f"Customer name not tagged unique: {customer['name']!r}"
            assert product["sku"], f"Product {product['name']} has no SKU"
            logger.info(f"UOM product: {product['name']}  SKU={product['sku']}")
            for t in self.tiers:
                logger.info(f"  tier={t['label']}  upc={t['upc']}  price=${t['price']}")
            allure.attach(
                "\n".join(f"{t['label']}  upc={t['upc']}  price=${t['price']}" for t in self.tiers),
                name="UOM tiers", attachment_type=allure.attachment_type.TEXT)

    # ---------------- Part 1: open Sales History -> Create Sale Order --- #
    @allure.title("Open Sales History and start a new sale order")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_02_open_create_sale_order(self):
        with allure.step("Dashboard -> hamburger -> Sales History -> + FAB"):
            assert self.dashboard.is_loaded(), "Dashboard not shown"
            sh = self.dashboard.go_to_sales_history()
            assert sh.is_loaded(), "Sales History did not open"
            TestUomMultiUnitSaleFulfillment.sales_history = sh
            TestUomMultiUnitSaleFulfillment.cso = sh.tap_create_sale_order()
            assert self.cso.is_loaded(), "Create Sale Order page did not open"

    # ---------------- Part 2: customer + order info -------------------- #
    @allure.title("Add customer and order information")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_03_customer_and_order_info(self):
        name = self.customer["name"]
        with allure.step(f"Select API customer '{name}' and verify it is applied"):
            self.cso.select_customer(name)
            assert self.cso.is_customer_selected(name), f"Customer {name} not selected"
        with allure.step("Order Type = Online, add unique internal + invoice notes, Next"):
            self.cso.set_order_type(CFG["order_type"])
            self.cso.set_internal_note(f"{CFG['internal_note_prefix']}-{self.customer['id']}")
            self.cso.set_invoice_note(f"{CFG['invoice_note_prefix']}-{self.customer['id']}")
            self.cso.tap_next()
            assert self.cso.is_product_step_loaded(), "Did not reach the product-selection step"

    # ---------------- Part 3: add all 4 UOM tiers as separate lines ---- #
    @allure.title("Add the UOM product's 4 tiers as 4 separate cart lines")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_04_add_product_all_uom_tiers(self):
        piece_qty = CFG["piece_qty"]
        with allure.step("Piece via search+Add To Cart, Pack/Case/Pallet via 'Add another unit'"):
            upcs = self.cso.add_product_all_uom_tiers(self.product, piece_qty=piece_qty)
            allure.attach(str(upcs), name="Tier UPCs added (Piece/Pack/Case/Pallet order)",
                          attachment_type=allure.attachment_type.TEXT)
            assert len(upcs) == 4, f"Expected 4 UOM tier lines, got {len(upcs)}: {upcs}"
            assert set(upcs) == {t["upc"] for t in self.tiers}, \
                f"Tier UPCs added {upcs} do not match the configured tiers {self.tiers}"

        # Piece gets `piece_qty` (set via the pre-Add-To-Cart stepper); the
        # other 3 tiers are fixed at qty=1 by the app itself (see
        # add_product_all_uom_tiers's own docstring) - validated as such,
        # not forced to a quantity the UI has no control for.
        subtotal = Decimal("0.00")
        with allure.step("Capture and verify each tier line's price x qty = subtotal"):
            # Captured LATEST-added-first (Pallet -> ... -> Piece): the cart
            # auto-scrolls to reveal each new line as it's added, so right
            # after adding all 4, Pallet (added last) is the one in view.
            # swipe_to's default direction only scrolls back UP the list
            # (toward earlier items) - confirmed live 2026-10-29, it never
            # found Pallet when this loop ran oldest-first, since that would
            # have needed scrolling the other way first.
            for t in reversed(self.tiers):
                t["qty"] = piece_qty if t["label"] == "Piece" else 1
                line = self.cso.get_cart_line(self.product["sku"], upc=t["upc"])
                expected_line = money(Decimal(str(t["price"])) * t["qty"])
                assert money(line["sub_total"]) == expected_line, (
                    f"Tier '{t['label']}' subtotal {line.get('sub_total')} != {expected_line} "
                    f"(price ${t['price']} x qty {t['qty']})")
                t["ui_sub_total"] = float(expected_line)
                subtotal += expected_line
                logger.info(f"✅ Tier '{t['label']}' line verified: ${t['price']} x {t['qty']} = ${expected_line}")
        TestUomMultiUnitSaleFulfillment.expected_subtotal = money(subtotal)
        allure.attach(str(self.tiers), name="Pre-Checkout Tier Captures",
                      attachment_type=allure.attachment_type.TEXT)
        with allure.step("Next -> Cart Summary"):
            TestUomMultiUnitSaleFulfillment.cart_summary = self.cso.tap_next_to_summary()

    # ---------------- Part 4: validate the cart summary --------------- #
    @allure.title("Validate the Cart Summary totals across all 4 UOM tier lines")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_05_validate_cart_summary(self):
        cs = self.cart_summary
        expected_qty = sum(t["qty"] for t in self.tiers)
        with allure.step("Total quantity (4 tiers), subtotal, discount, tax, grand total"):
            cs.scroll_to_summary()
            assert cs.get_total_quantity() == expected_qty, "Total Quantity mismatch across the 4 tier lines"
            assert money(cs.get_sub_total()) == self.expected_subtotal, (
                f"Sub Total {cs.get_sub_total()} != sum of all 4 tier lines {self.expected_subtotal}")
            assert money(cs.get_additional_discount()) == money(0), "Additional Discount is not $0.00"

            TestUomMultiUnitSaleFulfillment.tax = money(cs.get_tax())
            TestUomMultiUnitSaleFulfillment.grand_total = money(cs.get_grand_total())
            expected_grand = money(self.expected_subtotal + self.tax)
            assert self.grand_total == expected_grand, (
                f"Grand Total {self.grand_total} != subtotal {self.expected_subtotal} + tax {self.tax}")
            logger.info(f"Captured Grand Total = ${self.grand_total} (tax ${self.tax})")
        with allure.step("Proceed to Checkout"):
            TestUomMultiUnitSaleFulfillment.payment = cs.proceed_to_checkout()

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
            TestUomMultiUnitSaleFulfillment.sales_history = pay.tap_ok_return_to_sales_history()

    # ---------------- Part 6: validate in Sales History -------------- #
    @allure.title("Validate the new order in Sales History and capture its number")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_07_validate_sales_history(self):
        sh = self.sales_history
        with allure.step("Locate the newest card for the generated customer, capture Order Number"):
            order_no = sh.capture_latest_order_no(self.customer["name"])
            assert order_no.startswith("SO-"), f"Order number {order_no!r} not in SO- format"
            TestUomMultiUnitSaleFulfillment.order_no = order_no
            allure.attach(order_no, name="Order Number", attachment_type=allure.attachment_type.TEXT)
        with allure.step("Card fields: customer / Online / Paid / Pending / Sale Total == Grand Total"):
            card = sh.get_order_card(order_no)
            assert card.get("Business Name", "").strip() == self.customer["name"], "Business Name mismatch"
            assert card.get("Order Type") == "Online", f"Order Type = {card.get('Order Type')!r}"
            assert card.get("Invoice Status") == "Paid", f"Invoice Status = {card.get('Invoice Status')!r}"
            assert card.get("Status") == "Pending", f"Status = {card.get('Status')!r}"
            assert money(parse_currency(card.get("Sale Total", "0"))) == self.grand_total, (
                f"Sale Total {card.get('Sale Total')} != Grand Total {self.grand_total}")

    @allure.title("Validate the order via View Details - all 4 tier line totals present")
    @allure.severity(allure.severity_level.NORMAL)
    def test_08_validate_view_details(self):
        sh = self.sales_history
        with allure.step("Actions -> View Details, check order number / customer / totals"):
            details = sh.open_order_details(self.order_no)
            assert details.is_shown(), "Order Details did not open"
            ok, missing = details.contains_all(
                self.order_no,
                self.customer["name"],
                f"{self.grand_total:.2f}",
            )
            assert ok, f"Order Details missing expected values: {missing}"
        with allure.step("Every one of the 4 tier line totals appears on the invoice"):
            blob = details.read_all_text()
            assert self.product["name"] in blob, f"Product {self.product['name']!r} not in Order Details"
            missing_tiers = [
                t["label"] for t in self.tiers
                if f"{t['ui_sub_total']:.2f}" not in blob
            ]
            assert not missing_tiers, (
                f"Order Details is missing the line total for tier(s) {missing_tiers} "
                f"(expected amounts: { {t['label']: t['ui_sub_total'] for t in self.tiers} })")
            sh = details.go_back()
            TestUomMultiUnitSaleFulfillment.sales_history = sh

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
            TestUomMultiUnitSaleFulfillment.fulfillment = ful
        with allure.step("Open order -> Assign to me -> confirmation names the logged-in user"):
            msg = ful.assign_order_to_me(self.order_no)
            assert "assign" in msg.lower(), f"Unexpected assign message: {msg!r}"
            assert self.logged_in_user in msg, "Assign message does not name the logged-in user"
        with allure.step("The order now shows the logged-in user as picker"):
            assert ful.is_assigned_to(self.order_no, self.logged_in_user), \
                "Order is not shown as assigned to the logged-in user"

    # ---------------- Part 8: pick ---------------------------------- #
    @allure.title("Pick all 4 tier lines")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_10_pick_products(self):
        ful = self.fulfillment
        with allure.step("Re-open the order by number -> Start Picking"):
            ful.search(self.order_no)
            picking = ful.open_order_for_picking(self.order_no)
            picking.start_picking()
            TestUomMultiUnitSaleFulfillment.picking = picking
        with allure.step("Skip Scan Pick All -> Yes -> Pick; workflow advances to packing"):
            picking.skip_scan_pick_all()
            assert picking.is_all_picked(), "Workflow did not advance to the packing stage"

    # ---------------- Part 9: pack --------------------------------- #
    @allure.title("Pack all 4 tier lines")
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
    @allure.title("Confirm the same UOM order appears in the Packed section")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_12_validate_packed_section(self):
        with allure.step("Fulfillment opens; order has left the Pending section"):
            ful = self.dashboard.go_to_fulfillment()
            assert ful.is_loaded(), "Fulfillment did not open"
            still_pending = ful.is_order_in_pending(self.order_no)
            assert not still_pending, "Order still appears under Pending after packing"
        with allure.step("Open the Packed tab and locate the captured order number"):
            ful.open_packed()
            assert ful.is_packed_tab_selected(), "Packed tab is not the active tab"
            ful.search(self.order_no)
            assert ful.is_order_present(self.order_no), (
                f"Order {self.order_no} not found in the Packed section")
        with allure.step("The Packed card is the same order: number / customer / Online"):
            desc = ful.get_order_desc(self.order_no)
            assert self.order_no in desc, "Packed card order number mismatch"
            assert self.customer["name"] in desc, "Packed card shows the wrong customer"
            assert "Online" in desc, "Packed card Order Type is not Online"
            if "Picker Detail" in desc:
                assert self.logged_in_user in desc, "Packed card picker is not the logged-in user"
            allure.attach(desc, name="Packed order card (UOM)", attachment_type=allure.attachment_type.TEXT)
            try:
                shot = self.dashboard.take_screenshot("uom_packed_section_final")
                with open(shot, "rb") as fh:
                    allure.attach(fh.read(), name="Packed section (final)",
                                  attachment_type=allure.attachment_type.PNG)
            except Exception as e:
                logger.warning(f"Could not attach final Packed screenshot: {e}")
