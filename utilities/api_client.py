import random
import time
from datetime import datetime

import requests

from config.config_reader import ConfigReader
from utilities import test_data_names as names
from utilities.logger import get_logger

logger = get_logger(__name__)


class ApiClient:
    """Thin REST client against the KHUB backend the Admin app talks to.

    Ported from khub-pos-tests/utilities/api_client.py — same preprod tenant
    (`backend_api.preprod` in config/config.yaml), same endpoints. Used here
    to build test data (customer + products) for the mobile Sale Order /
    Fulfillment E2E without touching the UI, and to look up the generated
    order number as a fallback if the app doesn't surface it cleanly.

    The product/customer creation payloads were themselves ported into the
    POS suite from khub-web-tests' scripts/create_general_test_data_api.py.
    """

    def __init__(self, backend_name: str = "preprod"):
        self.config = ConfigReader().get_backend_api(backend_name)
        self.base = self.config["url"]
        self.session = requests.Session()
        self._login()

    # ── auth ─────────────────────────────────────────────────────────────
    def _login(self):
        resp = self.session.post(
            self.base + "/tenant/api/v1/core/user/authenticate",
            json={"username": self.config["username"], "password": self.config["password"]},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        entity = data.get("entity") or data.get("data") or {}
        token = (
            data.get("access_token")
            or data.get("token")
            or entity.get("access_token")
        )
        if not token:
            raise RuntimeError(f"No access token in authenticate response: {str(data)[:300]}")
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
        })
        # The login field (e.g. "preprod") and the profile's own display
        # username (e.g. "eaglews") are two different things - confirmed
        # live 2026-11-03, where an "Assign to me" confirmation named the
        # profile username, not the login. Callers that need to match an
        # app-displayed user name (assign/picker messages) should use this,
        # not the login credential.
        self.profile_username = (entity.get("user") or {}).get("username") or self.config["username"]
        logger.info(f"Authenticated against backend API as '{self.config['username']}' "
                    f"(profile username: '{self.profile_username}')")

    # ── catalog: category + channels + products ──────────────────────────
    def create_category(self, is_msa_compliant: bool = False, tag: str | None = None) -> dict:
        name, _ = names.category_name("admin", msa=is_msa_compliant, tag=tag)
        resp = self.session.post(
            self.base + "/tenant/api/v1/catalog/categories",
            json={
                "name": name,
                "parent_id": None,
                "code": None,
                "is_msa_compliant": is_msa_compliant,
                "visible_on_ecom": False,
                "slug": "",
                "seo_metadata": {"description": "", "title": ""},
                "description": "",
                "image": None,
                "imagesUploadLoading": False,
                # Confirmed live 2026-10-21: the backend now requires this
                # (a preprod catalog schema change, unrelated to this suite)
                # and only accepts exactly 18 or 21 - 0/null are rejected
                # even for a non-age-restricted category like this one.
                "age_threshold": 21,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        entity = data.get("entity") or data.get("data") or data
        category_id = entity.get("id")
        if not category_id:
            raise RuntimeError(f"Category created but ID not in response: {data}")
        logger.info(f"Created category '{name}' (id={category_id})")
        return {"id": category_id, "name": name}

    def get_channels(self) -> list[dict]:
        resp = self.session.get(
            self.base + "/tenant/api/v1/inventory/channel/list",
            params={"search_key": "", "page_size": -1},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        entities = data.get("entities") or data.get("data", {}).get("entities") or []
        if not entities:
            raise RuntimeError(f"No channels returned: {data}")
        entities.sort(key=lambda c: (not c.get("is_primary", False), c.get("id", 0)))
        return entities

    def create_product(
        self,
        category_id: int,
        channels: list[dict],
        price: float = 25.00,
        in_hand: int = 100,
        is_online: bool = True,
        tag: str | None = None,
    ) -> dict:
        """Create one sellable product priced at `price`, stocked `in_hand`
        per channel, SKU auto-generated. `is_online=True` keeps the product
        visible for an "Online" order type in the Admin app.

        Returns {id, name, sku, upc, price}. The SKU is resolved from the
        create response, or via a follow-up GET if the create response
        doesn't carry it.
        """
        name, _ = names.product_name("admin", tag=tag)
        upc = str(random.randint(1_000_000_000, 9_999_999_999))

        unit_price = {
            "base_cost": price * 0.6,
            "cost": price * 0.6,
            "margin": 10,
            "price": price,
            "lowest_selling_price": 0,
            "ecom_price": None,
            "upc": upc,
            "is_msa_upc": False,
            "definition": 1,
            "unit": 1,
            "subUnitId": None,
            "unitType": "Piece",
            "subUnit": "Unit",
            "margin_type": 1,
            "unit_price_tiers": [{"tier_id": i, "price": 0, "placeholder": f"Tier {i}"} for i in range(1, 6)],
            "unit_name": "Piece",
            "msrp_price": 0,
        }

        def _channel_entry(ch: dict, test_val: int) -> dict:
            return {
                "channel_name": ch["name"],
                "channel_id": ch["id"],
                "in_hand": in_hand,
                "on_hold": 0,
                "damaged": 0,
                "min_qty": 0,
                "max_qty": 0,
                "sold_by_unit": 1,
                "bought_by_unit": 1,
                "autoCalculate": False,
                "unit_prices": [unit_price],
                "ps_allowed_qty": None,
                "test": test_val,
            }

        channel_info = [_channel_entry(ch, i + 1) for i, ch in enumerate(channels)]

        slug = names.slugify(name)
        payload = {
            "name": name,
            "brand_id": None,
            "slug": slug,
            "auto_generate_sku": True,
            "auto_fetch_img": False,
            "is_tax_applicable": True,
            "back_order_portal": True,
            "back_order_ecom": False,
            "is_msa_compliant": False,
            "description": "",
            "desc_alter_by_client": False,
            "upc": upc,
            "upc_2": "",
            "upc_3": "",
            "mlc": "",
            "bin": "",
            "piece_definition": 1,
            "piece_upc": upc,
            "pack_definition": "",
            "pack_upc": "",
            "case_definition": "",
            "case_upc": "",
            "pallet_definition": "",
            "pallet_upc": "",
            "autoCalculate": True,
            "zone": "",
            "aisle": "",
            "gtn": "",
            "weight_unit": 2,
            "imagesUploadLoading": False,
            "images": [],
            "images_seo": [],
            "video_type": 5,
            "main_category_id": category_id,
            "min_qty": "",
            "max_qty": "",
            "status": 1,
            "is_online": is_online,
            "is_hot_seller": False,
            "is_featured": False,
            "is_new_arrival": False,
            "attributes": [],
            "attribute_groups": [],
            "unit_of_measurement": 10,
            "channel_info": channel_info,
            "product_seo_meta_data": {"description": "", "title": ""},
            "other_upcs": [],
            "ecom_name": None,
            "cost": 0,
            "base_cost": 0,
            "margin": 0,
            "category_ids": [category_id],
            "supplier_ids": [],
            "tag_values": [],
            "manufacturer_ids": [],
            # Same backend requirement as create_category (confirmed live
            # 2026-10-21) - only 18 or 21 are accepted, 0/null are rejected
            # even for a non-age-restricted product like this one.
            "age_threshold": 21,
        }

        resp = self.session.post(
            self.base + "/tenant/api/v1/catalog/products",
            json=payload,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Product '{name}' creation failed ({resp.status_code}): {resp.text[:400]}")
        data = resp.json()
        entity = data.get("entity") or data.get("data") or data
        product_id = entity.get("id") or entity.get("product_id")
        sku = self._extract_sku(entity) or (self.get_product(product_id) or {}).get("sku")
        logger.info(f"Created product '{name}' (id={product_id}, sku={sku}, upc={upc}, price=${price})")
        return {"id": product_id, "name": name, "sku": sku, "upc": upc, "price": price}

    def create_uom_product(
        self,
        category_id: int,
        channels: list[dict],
        pack_desc: str = "Box",
        case_desc: str = "Carton",
        pallet_desc: str = "Package",
        pack_qty: int = 5,
        case_qty: int = 6,
        pallet_qty: int = 30,
        base_cost: float = 10.0,
        in_hand: int = 20_000,
        tag: str | None = None,
    ) -> dict:
        """Create one product with 4 chained packaging tiers (Piece/Pack/
        Case/Pallet), custom Unit Desc labels on tiers 2-4, and a distinct
        UPC per tier - the same payload shape as khub-web-tests'
        scripts/create_uom_products_api.py (captured live from the UOM
        create-product flow): each tier's "definition" is the quantity of
        the tier below it (case_qty=6 means "6 Packs per Case", not "6
        Pieces"), and subUnitId chains the same way. margin = 25% of cost,
        price = cost + margin, scaled up per tier.

        Returns {id, name, sku, piece_upc, pack_upc, case_upc, pallet_upc,
        piece_desc, pack_desc, case_desc, pallet_desc, pack_qty, case_qty,
        pallet_qty, piece_price, pack_price, case_price, pallet_price}.
        """
        name, _ = names.product_name("admin", tag=tag)
        # The backend rejects unit_name over 50 chars (confirmed live
        # 2026-10-29) - the generated name + QA tag routinely exceeds that,
        # so the Piece tier's label is truncated rather than reusing it whole.
        piece_desc = name[:50]
        piece_upc = str(random.randint(1_000_000_000, 9_999_999_999))
        pack_upc = str(random.randint(1_000_000_000, 9_999_999_999))
        case_upc = str(random.randint(1_000_000_000, 9_999_999_999))
        pallet_upc = str(random.randint(1_000_000_000, 9_999_999_999))

        margin_ratio = 0.25

        def _tier_list():
            return [{"tier_id": i, "price": 0, "placeholder": f"Tier {i}"} for i in range(1, 6)]

        def _unit_price(cost, upc, definition, unit, sub_unit_id, unit_type, sub_unit, unit_name):
            margin = round(cost * margin_ratio, 2)
            return {
                "base_cost": cost, "cost": cost, "margin": margin, "price": round(cost + margin, 2),
                "lowest_selling_price": 0, "ecom_price": None if unit == 1 else 0,
                "upc": upc, "is_msa_upc": unit == 1, "definition": definition, "unit": unit,
                "subUnitId": sub_unit_id, "unitType": unit_type, "subUnit": sub_unit,
                "margin_type": 1, "unit_price_tiers": _tier_list(), "unit_name": unit_name,
                "msrp_price": 0,
            }

        pack_cost = base_cost * pack_qty
        case_cost = pack_cost * case_qty
        pallet_cost = case_cost * pallet_qty

        unit_prices = [
            _unit_price(base_cost, piece_upc, 1, 1, None, "Piece", "Unit", piece_desc),
            _unit_price(pack_cost, pack_upc, pack_qty, 2, 1, "Pack", "Pieces", pack_desc),
            _unit_price(case_cost, case_upc, case_qty, 3, 2, "Case", "Packs", case_desc),
            _unit_price(pallet_cost, pallet_upc, pallet_qty, 4, 3, "Pallet", "Cases", pallet_desc),
        ]

        def _channel_entry(ch: dict, test_val: int, stock: int) -> dict:
            return {
                "channel_name": ch["name"], "channel_id": ch["id"], "in_hand": stock,
                "on_hold": 0, "damaged": 0, "min_qty": 0, "max_qty": 0,
                "sold_by_unit": 1, "bought_by_unit": 1, "autoCalculate": False,
                "unit_prices": unit_prices, "ps_allowed_qty": None, "test": test_val,
            }

        channel_info = [
            _channel_entry(ch, i + 1, in_hand if i == 0 else 0)
            for i, ch in enumerate(channels)
        ]

        payload = {
            "name": name, "brand_id": None, "slug": names.slugify(name),
            "auto_generate_sku": True, "auto_fetch_img": False, "is_tax_applicable": True,
            "back_order_portal": True, "back_order_ecom": False, "is_msa_compliant": False,
            "description": "", "desc_alter_by_client": False,
            "upc": piece_upc, "upc_2": "", "upc_3": "", "mlc": "", "bin": "",
            "piece_definition": 1, "piece_upc": piece_upc,
            "pack_definition": pack_qty, "pack_upc": pack_upc,
            "case_definition": case_qty, "case_upc": case_upc,
            "pallet_definition": pallet_qty, "pallet_upc": pallet_upc,
            "autoCalculate": True, "zone": "", "aisle": "", "gtn": "", "weight_unit": 2,
            "imagesUploadLoading": False, "images": [], "images_seo": [], "video_type": 5,
            "main_category_id": category_id, "min_qty": "", "max_qty": "", "status": 1,
            "is_online": True, "is_hot_seller": False, "is_featured": False, "is_new_arrival": False,
            "attributes": [], "attribute_groups": [], "unit_of_measurement": 10,
            "channel_info": channel_info,
            "product_seo_meta_data": {"description": "", "title": ""},
            "other_upcs": [piece_upc], "requiredDef": [], "ecom_name": None,
            "cost": 0, "base_cost": 0, "margin": 0,
            "category_ids": [category_id], "supplier_ids": [], "tag_values": [], "manufacturer_ids": [],
            "age_threshold": 21,
        }

        resp = self.session.post(self.base + "/tenant/api/v1/catalog/products", json=payload, timeout=30)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"UOM product '{name}' creation failed ({resp.status_code}): {resp.text[:400]}")
        data = resp.json()
        entity = data.get("entity") or data.get("data") or data
        product_id = entity.get("id") or entity.get("product_id")
        sku = self._extract_sku(entity) or (self.get_product(product_id) or {}).get("sku")
        logger.info(
            f"Created UOM product '{name}' (id={product_id}, sku={sku}) tiers: "
            f"Piece/{pack_desc}({pack_qty})/{case_desc}({case_qty})/{pallet_desc}({pallet_qty})"
        )
        return {
            "id": product_id, "name": name, "sku": sku,
            "piece_upc": piece_upc, "pack_upc": pack_upc, "case_upc": case_upc, "pallet_upc": pallet_upc,
            "piece_desc": piece_desc, "pack_desc": pack_desc, "case_desc": case_desc, "pallet_desc": pallet_desc,
            "pack_qty": pack_qty, "case_qty": case_qty, "pallet_qty": pallet_qty,
            "piece_price": round(base_cost + round(base_cost * margin_ratio, 2), 2),
            "pack_price": round(pack_cost + round(pack_cost * margin_ratio, 2), 2),
            "case_price": round(case_cost + round(case_cost * margin_ratio, 2), 2),
            "pallet_price": round(pallet_cost + round(pallet_cost * margin_ratio, 2), 2),
        }

    @staticmethod
    def _extract_sku(entity: dict) -> str | None:
        for key in ("sku", "product_sku", "sku_code"):
            if entity.get(key):
                return str(entity[key])
        # SKU commonly lives on the first channel_info / unit_price entry
        for ch in entity.get("channel_info") or []:
            if ch.get("sku"):
                return str(ch["sku"])
            for up in ch.get("unit_prices") or []:
                if up.get("sku"):
                    return str(up["sku"])
        return None

    def get_product(self, product_id) -> dict | None:
        if not product_id:
            return None
        resp = self.session.get(
            self.base + f"/tenant/api/v1/catalog/products/{product_id}",
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning(f"get_product({product_id}) -> {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        entity = data.get("entity") or data.get("data") or data
        return {
            "id": entity.get("id"),
            "name": entity.get("name"),
            "sku": self._extract_sku(entity),
            "upc": entity.get("upc"),
            "raw": entity,
        }

    def get_product_by_upc(self, upc: str, timeout: int = 60) -> dict | None:
        """Look up a product's backend id/SKU by UPC via the live catalog
        search (list3). Needed for promotion-scenario products: their test
        data file (utilities/promotion_data.py) carries only UPCs, since
        they're created by a sibling repo's script, not this project's own
        create_uom_product. Retries for `timeout`s since a just-created
        product can briefly lag the search index (same class of delay
        CreateSaleOrderPage.add_product_by_sku already works around on the
        UI side)."""
        url = self.base + "/tenant/api/v1/catalog/products/list3"
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self.session.get(url, params={
                "search_key": upc, "is_group": 0, "page": 1, "page_size": 5,
                "channel_id": 1, "category_ids": "", "brand_ids": "",
                "show_default": "", "statuses": 1,
            }, timeout=30)
            resp.raise_for_status()
            entities = resp.json().get("entities") or []
            if entities:
                e = entities[0]
                return {"id": e.get("id"), "sku": e.get("sku"), "name": e.get("name"), "raw": e}
            time.sleep(3)
        return None

    # ── customer ────────────────────────────────────────────────────────
    def create_customer(self, is_msa_compliant: bool = False, tag: str | None = None) -> dict:
        name, _ = names.customer_name("admin", tag=tag)
        email = names.customer_email(name)
        phone = f"+1 (555) {random.randint(100, 999)}-{random.randint(1000, 9999)}"
        phone_digits = phone.replace("+", "").replace(" ", "").replace("(", "").replace(")", "").replace("-", "")

        payload = {
            "name": name,
            "no": None,
            "email": email,
            "alternate_email": None,
            "skip_shipping_billing": True,
            "tier_id": None,
            "phone_no": None,
            "business_no": None,
            "business_name": name,
            "business_city": None,
            "password": "Password@123",
            "business_state": None,
            "business_phone_no": phone,
            "whatsapp_no": phone_digits,
            "date_of_join": None,
            "balance_limit_check": False,
            "excluded_product_ids": [],
            "is_msa_compliant": is_msa_compliant,
            "is_active": True,
            "customer_type": None,
            "dba_name": name,
            "address": None,
            "sale_agent": "",
            "business_tax_no": None,
            "business_tax_expiry_date": None,
            "allow_ecom": "N",
            "promotion_acceptance": "Y",
            "class_of_trades": "Retailer",
            "invoice_aging": 0,
            "custom_status": False,
            "note": None,
            "out_of_state": False,
            "is_exempt_from_tax": "N",
            "tax_ids": [],
            "all_taxes_applicable": True,
            "restricted_category_ids": [],
            "allowed_category_ids": [],
            "category_access_type": None,
            "restricted_product_ids": [],
            "sale_agent_id": None,
            "sale_agent_obj": {"key": None, "value": None, "label": "Select User"},
            "resale_certificate_expiry": None,
            "business_certificate_expiry": None,
            "tobacco_license_expiry": None,
            "state_id_license_expiry": None,
            "is_whatsapp_customer": False,
            "customer_shipping_details": {
                "name": name,
                "company_name": name,
                "telephone_num": phone,
                "address": "4545 Ludtano Ln",
                "country": "United States",
                "county": "BALTIMORE CITY",
                "city": "Aberdeen Proving Ground",
                "state": "MARYLAND",
                "zip_code": "21001",
                "shipping_no": None,
                "tax_jurisdiction": "MARYLAND",
                "is_billing_same": "Y",
            },
            "customer_billing_details": {
                "name": name,
                "company_name": name,
                "telephone_num": phone,
                "address": "4545 Ludtano Ln",
                "country": "United States",
                "county": "BALTIMORE CITY",
                "city": "Aberdeen Proving Ground",
                "state": "MARYLAND",
                "zip_code": "21001",
            },
            "resale_certificate_num": None,
            "resale_certificate": None,
            "business_certificate": None,
            "business_certificate_num": None,
            "state_id_license": None,
            "state_id_license_num": None,
            "tobacco_license": None,
            "tobacco_license_num": None,
            "county": "",
            "billing_email": None,
            "tax_expiry_date": None,
        }

        resp = self.session.post(
            self.base + "/tenant/api/v1/sale/customers",
            json=payload,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Customer creation failed ({resp.status_code}): {resp.text[:400]}")
        data = resp.json()
        entity = data.get("entity") or data.get("data") or data
        customer_id = entity.get("id") or entity.get("customer_id")
        customer_no = entity.get("no") or entity.get("customer_no")
        logger.info(f"Created customer '{name}' (id={customer_id}, no={customer_no}, phone={phone})")
        return {"id": customer_id, "no": customer_no, "name": name, "phone": phone, "email": email}

    # ── one-call test-data bundle for the Online sale E2E ──
    def create_online_sale_test_data(self, prices: list[float], quantities: list[int],
                                     count: int) -> dict:
        """Create one customer + `count` sellable products (SKU auto-generated,
        100 in stock, is_online=True). `prices` / `quantities` are cycled if
        shorter than `count`. Returns a dict the test stores as its context:
        {customer, category, products:[{id,name,sku,upc,price,qty,line_subtotal}],
         expected_subtotal}."""
        from decimal import ROUND_HALF_UP, Decimal

        # Each record gets its own QA-<date>-<time>-<rand> tag so every name is
        # individually unique; they still share the run's date/time so it is
        # obvious they were generated together.
        category = self.create_category()
        channels = self.get_channels()
        products = []
        subtotal = Decimal("0.00")
        for i in range(count):
            price = float(prices[i % len(prices)])
            qty = int(quantities[i % len(quantities)])
            p = self.create_product(category["id"], channels, price=price)
            line = (Decimal(str(price)) * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            subtotal += line
            p["qty"] = qty
            p["line_subtotal"] = float(line)
            products.append(p)
        customer = self.create_customer()
        return {
            "customer": customer,
            "category": category,
            "products": products,
            "expected_subtotal": float(subtotal),
        }

    # ── order lookup (fallback for capturing the generated order number) ──
    def get_order_number_for_customer(self, customer_name: str) -> str | None:
        """Best-effort: return the `no` (e.g. "SO-260903-12345") of the most
        recent sale order whose customer/business name matches. Used only as
        a fallback when the app UI doesn't cleanly surface the order number."""
        resp = self.session.get(
            self.base + "/tenant/api/v1/sale/order/list2",
            params={"page": 1, "page_size": 10, "search_key": customer_name},
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning(f"order/list2 lookup -> {resp.status_code}: {resp.text[:200]}")
            return None
        entities = resp.json().get("entities") or []
        for e in entities:
            hay = " ".join(str(e.get(k, "")) for k in ("customer_name", "business_name", "customer"))
            if customer_name in hay:
                return e.get("no")
        return entities[0].get("no") if entities else None

    # ── product labels (Label Management) ──────────────────────────────
    # Separate from create_product/create_uom_product on purpose - those
    # stay untouched. Reverse-engineered live 2026-11-12 from the portal's
    # own "Add Label" picker (Product Catalog > Products, list screen):
    # GET .../catalog/tags/list?tag_type=1&status=1&page_size=-1 lists every
    # Product-type label ({id, value, tag_type, color, bg_color,
    # description, status, external_details:{show_on_fulfillment,
    # show_on_invoice}}), and PUT .../catalog/products/{id}/labels with
    # {"tag_ids": [...]} sets a product's full label set (a replace, not a
    # toggle - resend every id the product should end up with).
    def create_product_label(
        self,
        label_name: str,
        bg_color: str = "#817CDB",
        text_color: str = "#FFFFFF",
        show_on_fulfillment: bool = True,
        show_on_invoice: bool = True,
        description: str = "Created via API for automated test data",
    ) -> dict:
        """Create a Product-type Label Management label (tag_type=1) via
        the backend directly - same `Create Label` form the portal's
        Product Catalog > Products list and the mobile app's Label
        Management screen both use. Reverse-engineered live 2026-11-12 from
        the portal's own "Create New Label" modal:
        POST .../catalog/tags/v2 {value, tag_type, color, bg_color, status,
        description, show_on_fulfillment, show_on_invoice}. Avoids needing
        to drive the mobile UI (tests/labels/test_label_management_create_label.py)
        just to get a label to assign to a product.

        Returns {id, name, bg_color, text_color}."""
        payload = {
            "value": label_name,
            "tag_type": 1,
            "color": text_color,
            "bg_color": bg_color,
            "status": 1,
            "description": description,
            "show_on_fulfillment": show_on_fulfillment,
            "show_on_invoice": show_on_invoice,
        }
        resp = self.session.post(self.base + "/tenant/api/v1/catalog/tags/v2", json=payload, timeout=30)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Label '{label_name}' creation failed ({resp.status_code}): {resp.text[:400]}")
        data = resp.json()
        entity = data.get("entity") or data.get("data") or data
        label_id = entity.get("id")
        if not label_id:
            raise RuntimeError(f"Label created but ID not in response: {data}")
        logger.info(f"Created Product label '{label_name}' (id={label_id}, bg={bg_color}, text={text_color})")
        return {"id": label_id, "name": label_name, "bg_color": bg_color, "text_color": text_color}

    def get_product_label_id(self, label_name: str) -> int | None:
        """Resolve a Label Management label's id by its exact name (the
        `value` field), searching active Product-type (tag_type=1) labels
        only - i.e. the labels tests/labels/test_label_management_create_label.py
        creates. Returns None if no active label has that exact name."""
        resp = self.session.get(
            self.base + "/tenant/api/v1/catalog/tags/list",
            params={"tag_type": 1, "status": 1, "page_size": -1},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        entities = data.get("entities") or data.get("data", {}).get("entities") or []
        for tag in entities:
            if tag.get("value") == label_name:
                return tag.get("id")
        return None

    def set_product_labels(self, product_id: int, tag_ids: list[int]) -> None:
        """Set a product's full label set (replaces whatever was assigned
        before - pass every tag_id the product should end up with, not just
        the one being added)."""
        resp = self.session.put(
            self.base + f"/tenant/api/v1/catalog/products/{product_id}/labels",
            json={"tag_ids": tag_ids},
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Setting labels {tag_ids} on product {product_id} failed "
                f"({resp.status_code}): {resp.text[:400]}"
            )
        logger.info(f"Set labels {tag_ids} on product {product_id}")

    def create_product_with_label(
        self,
        category_id: int,
        channels: list[dict],
        label_name: str,
        price: float = 25.00,
        in_hand: int = 100,
        is_online: bool = True,
        tag: str | None = None,
    ) -> dict:
        """Create a sellable product (same shape/defaults as create_product,
        which this calls unmodified) and assign it the named, pre-existing
        Product label by name (e.g. one created via
        tests/labels/test_label_management_create_label.py). Exists to give
        Label Management Phase 2+ a product to work with without touching
        the UI's own (currently broken - see CLAUDE.md) Category picker.

        Raises RuntimeError if no active label named `label_name` exists.
        Returns create_product's dict plus {"label_id", "label_name"}."""
        label_id = self.get_product_label_id(label_name)
        if label_id is None:
            raise RuntimeError(
                f"No active Product label named '{label_name}' found via "
                f"catalog/tags/list - create it first (Label Management)."
            )
        product = self.create_product(
            category_id, channels, price=price, in_hand=in_hand,
            is_online=is_online, tag=tag,
        )
        self.set_product_labels(product["id"], [label_id])
        product["label_id"] = label_id
        product["label_name"] = label_name
        logger.info(f"Assigned label '{label_name}' (id={label_id}) to product {product['id']}")
        return product

    def create_product_with_new_label(
        self,
        category_id: int,
        channels: list[dict],
        bg_color: str = "#817CDB",
        text_color: str = "#FFFFFF",
        price: float = 25.00,
        in_hand: int = 100,
        is_online: bool = True,
        tag: str | None = None,
    ) -> dict:
        """One-call test-data builder: creates a brand-new Product label
        (create_product_label) and a brand-new product carrying it
        (create_product_with_label) - no live UI needed for either. Each
        run gets its own unique label, same generated-name convention as
        the rest of this suite, so runs never collide or reuse each
        other's labels.

        Returns create_product_with_label's dict (id, name, sku, upc,
        price, label_id, label_name) plus {"label_bg_color", "label_text_color"}."""
        label_name = f"Halvik {names.new_tag()}"
        label = self.create_product_label(
            label_name, bg_color=bg_color, text_color=text_color,
            description="Automation test product label",
        )
        product = self.create_product_with_label(
            category_id, channels, label["name"],
            price=price, in_hand=in_hand, is_online=is_online, tag=tag,
        )
        product["label_bg_color"] = label["bg_color"]
        product["label_text_color"] = label["text_color"]
        return product

    # ── tier pricing + promotions (Customer Tier vs Promotion scenario) ────
    # Separate from create_product/create_customer on purpose - those stay
    # untouched. Reverse-engineered live 2026-11-13 from the portal's own
    # Add Customer form ("Tier" dropdown: Tier 1-5 / None, Basic Details
    # section) and a product's Define Pricing grid ("Tier 1 SP ($)" ...
    # "Tier 5 SP ($)" columns). Both fields already existed, unused, in
    # create_customer's payload (`"tier_id": None`) and create_product's
    # per-unit-price payload (`"unit_price_tiers": [{"tier_id": i, "price":
    # 0, ...} for i in range(1, 6)]`) - confirmed live via a throwaway probe
    # that POSTing non-zero unit_price_tiers prices and a non-null
    # customer tier_id (plain integers 1-5, no separate tier-list endpoint
    # exists - the dropdown is a fixed client-side enum) both round-trip
    # correctly on GET.
    def create_customer_with_tier(self, tier_id: int, is_msa_compliant: bool = False,
                                   tag: str | None = None) -> dict:
        """Same as create_customer, plus a Tier assignment (1-5). A
        customer with a tier gets that tier's Tier <n> SP price on any
        product that defines one, in place of its regular Sale Price -
        see create_product_with_tier_prices."""
        name, _ = names.customer_name("admin", tag=tag)
        email = names.customer_email(name)
        phone = f"+1 (555) {random.randint(100, 999)}-{random.randint(1000, 9999)}"
        phone_digits = phone.replace("+", "").replace(" ", "").replace("(", "").replace(")", "").replace("-", "")

        payload = {
            "name": name,
            "no": None,
            "email": email,
            "alternate_email": None,
            "skip_shipping_billing": True,
            "tier_id": tier_id,
            "phone_no": None,
            "business_no": None,
            "business_name": name,
            "business_city": None,
            "password": "Password@123",
            "business_state": None,
            "business_phone_no": phone,
            "whatsapp_no": phone_digits,
            "date_of_join": None,
            "balance_limit_check": False,
            "excluded_product_ids": [],
            "is_msa_compliant": is_msa_compliant,
            "is_active": True,
            "customer_type": None,
            "dba_name": name,
            "address": None,
            "sale_agent": "",
            "business_tax_no": None,
            "business_tax_expiry_date": None,
            "allow_ecom": "N",
            "promotion_acceptance": "Y",
            "class_of_trades": "Retailer",
            "invoice_aging": 0,
            "custom_status": False,
            "note": None,
            "out_of_state": False,
            "is_exempt_from_tax": "N",
            "tax_ids": [],
            "all_taxes_applicable": True,
            "restricted_category_ids": [],
            "allowed_category_ids": [],
            "category_access_type": None,
            "restricted_product_ids": [],
            "sale_agent_id": None,
            "sale_agent_obj": {"key": None, "value": None, "label": "Select User"},
            "resale_certificate_expiry": None,
            "business_certificate_expiry": None,
            "tobacco_license_expiry": None,
            "state_id_license_expiry": None,
            "is_whatsapp_customer": False,
            "customer_shipping_details": {
                "name": name,
                "company_name": name,
                "telephone_num": phone,
                "address": "4545 Ludtano Ln",
                "country": "United States",
                "county": "BALTIMORE CITY",
                "city": "Aberdeen Proving Ground",
                "state": "MARYLAND",
                "zip_code": "21001",
                "shipping_no": None,
                "tax_jurisdiction": "MARYLAND",
                "is_billing_same": "Y",
            },
            "customer_billing_details": {
                "name": name,
                "company_name": name,
                "telephone_num": phone,
                "address": "4545 Ludtano Ln",
                "country": "United States",
                "county": "BALTIMORE CITY",
                "city": "Aberdeen Proving Ground",
                "state": "MARYLAND",
                "zip_code": "21001",
            },
            "resale_certificate_num": None,
            "resale_certificate": None,
            "business_certificate": None,
            "business_certificate_num": None,
            "state_id_license": None,
            "state_id_license_num": None,
            "tobacco_license": None,
            "tobacco_license_num": None,
            "county": "",
            "billing_email": None,
            "tax_expiry_date": None,
        }

        resp = self.session.post(
            self.base + "/tenant/api/v1/sale/customers",
            json=payload,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Customer creation failed ({resp.status_code}): {resp.text[:400]}")
        data = resp.json()
        entity = data.get("entity") or data.get("data") or data
        customer_id = entity.get("id") or entity.get("customer_id")
        customer_no = entity.get("no") or entity.get("customer_no")
        logger.info(f"Created customer '{name}' (id={customer_id}, no={customer_no}, tier_id={tier_id})")
        return {"id": customer_id, "no": customer_no, "name": name, "phone": phone,
                "email": email, "tier_id": tier_id}

    def create_product_with_tier_prices(
        self,
        category_id: int,
        channels: list[dict],
        tier_prices: dict,
        price: float = 250.00,
        in_hand: int = 100,
        is_online: bool = True,
        tag: str | None = None,
    ) -> dict:
        """Same as create_product, plus non-zero Tier <n> SP prices (1-5)
        on its single Piece unit. `tier_prices` maps tier_id (1-5) -> price;
        any tier not given keeps the product's default of 0 (no override
        for that tier). Returns create_product's usual dict plus
        {"tier_prices": tier_prices}."""
        name, _ = names.product_name("admin", tag=tag)
        upc = str(random.randint(1_000_000_000, 9_999_999_999))

        unit_price = {
            "base_cost": price * 0.6,
            "cost": price * 0.6,
            "margin": 10,
            "price": price,
            "lowest_selling_price": 0,
            "ecom_price": None,
            "upc": upc,
            "is_msa_upc": False,
            "definition": 1,
            "unit": 1,
            "subUnitId": None,
            "unitType": "Piece",
            "subUnit": "Unit",
            "margin_type": 1,
            "unit_price_tiers": [
                {"tier_id": i, "price": tier_prices.get(i, 0), "placeholder": f"Tier {i}"}
                for i in range(1, 6)
            ],
            "unit_name": "Piece",
            "msrp_price": 0,
        }

        def _channel_entry(ch: dict, test_val: int) -> dict:
            return {
                "channel_name": ch["name"],
                "channel_id": ch["id"],
                "in_hand": in_hand,
                "on_hold": 0,
                "damaged": 0,
                "min_qty": 0,
                "max_qty": 0,
                "sold_by_unit": 1,
                "bought_by_unit": 1,
                "autoCalculate": False,
                "unit_prices": [unit_price],
                "ps_allowed_qty": None,
                "test": test_val,
            }

        channel_info = [_channel_entry(ch, i + 1) for i, ch in enumerate(channels)]

        slug = names.slugify(name)
        payload = {
            "name": name,
            "brand_id": None,
            "slug": slug,
            "auto_generate_sku": True,
            "auto_fetch_img": False,
            "is_tax_applicable": True,
            "back_order_portal": True,
            "back_order_ecom": False,
            "is_msa_compliant": False,
            "description": "",
            "desc_alter_by_client": False,
            "upc": upc,
            "upc_2": "",
            "upc_3": "",
            "mlc": "",
            "bin": "",
            "piece_definition": 1,
            "piece_upc": upc,
            "pack_definition": "",
            "pack_upc": "",
            "case_definition": "",
            "case_upc": "",
            "pallet_definition": "",
            "pallet_upc": "",
            "autoCalculate": True,
            "zone": "",
            "aisle": "",
            "gtn": "",
            "weight_unit": 2,
            "imagesUploadLoading": False,
            "images": [],
            "images_seo": [],
            "video_type": 5,
            "main_category_id": category_id,
            "min_qty": "",
            "max_qty": "",
            "status": 1,
            "is_online": is_online,
            "is_hot_seller": False,
            "is_featured": False,
            "is_new_arrival": False,
            "attributes": [],
            "attribute_groups": [],
            "unit_of_measurement": 10,
            "channel_info": channel_info,
            "product_seo_meta_data": {"description": "", "title": ""},
            "other_upcs": [],
            "ecom_name": None,
            "cost": 0,
            "base_cost": 0,
            "margin": 0,
            "category_ids": [category_id],
            "supplier_ids": [],
            "tag_values": [],
            "manufacturer_ids": [],
            "age_threshold": 21,
        }

        resp = self.session.post(
            self.base + "/tenant/api/v1/catalog/products",
            json=payload,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Product '{name}' creation failed ({resp.status_code}): {resp.text[:400]}")
        data = resp.json()
        entity = data.get("entity") or data.get("data") or data
        product_id = entity.get("id") or entity.get("product_id")
        sku = self._extract_sku(entity) or (self.get_product(product_id) or {}).get("sku")
        logger.info(f"Created product '{name}' (id={product_id}, sku={sku}, upc={upc}, "
                    f"price=${price}, tier_prices={tier_prices})")
        return {"id": product_id, "name": name, "sku": sku, "upc": upc, "price": price,
                "tier_prices": tier_prices}

    def create_promotion(
        self,
        product_id: int,
        channel_id: int,
        reward_percent: float,
        trigger_qty: int = 1,
        max_reward_qty: int = 100,
        unit: int = 1,
        name: str | None = None,
    ) -> dict:
        """Create a Basic (single-product, percent-off) promotion - same
        payload shape reverse-engineered for khub-web-tests'
        create_mobile_promotion_scenarios_api.py (promotion_type=1,
        trigger_sources == reward_sources for a single-product Basic
        promo, unit=1 is Piece). Kept local to this project (rather than
        reusing that sibling script) because it targets a product this
        project creates itself (with tier prices) - not one of the
        sibling repo's own fixed scenario products.

        Returns {"id", "name"}."""
        name = name or f"Mobile_TierVsPromo_{random.randint(100000, 999999)}"
        detail = {
            "id": None,
            "trigger_qty": trigger_qty,
            "max_reward_qty": max_reward_qty,
            "reward_value_type": 1,  # percent
            "reward_value": reward_percent,
            "max_repeats_per_order": None,
            "trigger_sources": [{"source_entity_name": "products", "source_id": product_id, "unit": unit}],
            "reward_sources": [{"source_entity_name": "products", "source_id": product_id, "unit": unit}],
        }
        payload = {
            "name": name,
            "start_datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            "end_datetime": None,
            "has_sale_badge": False,
            "sale_badge_template": None,
            "display_counter": False,
            "counter_duration": None,
            "counter_template": 2,
            "applicable_for": 2,
            "customer_group_ids": [],
            "applicable_to": 1,  # All Customers
            "promotion_details": [detail],
            "channel_id": channel_id,
            "promotion_type": 1,  # Basic
            "funding_manufacturer_percent": 0,
            "tax_basis": 1,
            "is_scan_report_eligible": False,
            "report_destination": None,
        }
        resp = self.session.post(
            self.base + "/tenant/api/v1/marketing/promotions",
            json=payload,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Promotion '{name}' creation failed ({resp.status_code}): {resp.text[:400]}")
        data = resp.json()
        entity = data.get("entity") or data.get("data") or data
        promo_id = entity.get("id")
        logger.info(f"Created promotion '{name}' (id={promo_id}) on product {product_id}, "
                    f"{reward_percent}% off, qty {trigger_qty}-{max_reward_qty}")
        return {"id": promo_id, "name": name}
