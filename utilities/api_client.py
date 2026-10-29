import random

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
        token = (
            data.get("access_token")
            or data.get("token")
            or data.get("entity", {}).get("access_token")
            or data.get("data", {}).get("access_token")
        )
        if not token:
            raise RuntimeError(f"No access token in authenticate response: {str(data)[:300]}")
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
        })
        logger.info(f"Authenticated against backend API as '{self.config['username']}'")

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
