"""Realistic-but-unique names for API-generated test data.

Every generated record gets a human-plausible name (a real-sounding wholesale
business or grocery product) followed by a `QA-<YYMMDD>-<HHMMSS>-<rand>` tag so
it is unmistakably automation data and unique per run, while still reading
sensibly in the app UI and in reports.

Kept byte-for-byte identical in each KHub suite's `utilities/` - the suites are
deliberately independent copies (see each CLAUDE.md), so there is no shared
package to import from.

  name, tag = customer_name("admin")
  -> ("Cedar Point Provisions LLC QA-260903-181530-K4X9", "QA-260903-181530-K4X9")
"""
import random
import re
import string
from datetime import datetime

# --- realistic word banks -------------------------------------------------
_BIZ_PLACE = (
    "Cedar Point", "Blue Ridge", "Riverside", "Silver Lake", "Harbor View",
    "Maple Grove", "Stonebridge", "Willow Creek", "Northgate", "Great Lakes",
    "Sunset Valley", "Iron Mountain", "Clearwater", "Fox Hollow", "Pine Bluff",
)
_BIZ_TRADE = (
    "Provisions", "Trading", "Wholesale", "Distributors", "Grocery", "Supply",
    "Mercantile", "Foods", "Market", "Beverage", "Import", "Fresh Market",
)
_BIZ_ENTITY = ("LLC", "Inc", "Co", "Corp", "Group", "Partners")

_PROD_BRAND = (
    "Cascade Farms", "Northwind", "Silverpeak", "Harvest Lane", "Copper Kettle",
    "Sungrove", "Timberline", "Bayside", "Ironwood", "Larkspur", "Old Mill",
    "Golden Field", "Riverstone", "Whitecap", "Cedar Creek",
)
_PROD_ITEM = (
    "Sparkling Water", "Roasted Almonds", "Cold Brew Coffee", "Trail Mix",
    "Extra Virgin Olive Oil", "Granola Bars", "Green Tea", "Maple Syrup",
    "Hot Sauce", "Sea Salt Chips", "Sourdough Crackers", "Honey", "Salsa",
    "Sparkling Lemonade", "Dark Chocolate",
)
_PROD_ITEM_MSA = (
    "Filtered Cigars", "Pipe Tobacco", "Natural Leaf Cigars", "Rolling Tobacco",
    "Cigarillos", "Snuff Tobacco",
)
_PROD_SIZE = ("8 oz", "12 oz", "16 oz", "500 ml", "1 L", "6 pack", "24 ct", "2 lb")


def _rand(n: int = 4) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def new_tag() -> str:
    """A fresh unique, search-safe tag: QA-<YYMMDD>-<HHMMSS>-<RAND4>."""
    return f"QA-{datetime.now():%y%m%d-%H%M%S}-{_rand()}"


def customer_name(source: str = "qa", tag: str | None = None) -> tuple[str, str]:
    """Returns (business_name, tag). `source` is accepted for call-site clarity
    and kept out of the visible name so it stays realistic."""
    tag = tag or new_tag()
    name = (f"{random.choice(_BIZ_PLACE)} {random.choice(_BIZ_TRADE)} "
            f"{random.choice(_BIZ_ENTITY)} {tag}")
    return name, tag


def product_name(source: str = "qa", msa: bool = False, tag: str | None = None) -> tuple[str, str]:
    tag = tag or new_tag()
    items = _PROD_ITEM_MSA if msa else _PROD_ITEM
    name = (f"{random.choice(_PROD_BRAND)} {random.choice(items)} "
            f"{random.choice(_PROD_SIZE)} {tag}")
    return name, tag


def category_name(source: str = "qa", msa: bool = False, tag: str | None = None) -> tuple[str, str]:
    tag = tag or new_tag()
    label = "Tobacco Products" if msa else "General Merchandise"
    return f"{label} {tag}", tag


def customer_email(business_name: str) -> str:
    """A plausible purchasing address derived from the business name, made
    unique by a random token (some suites look customers up by email)."""
    slug = re.sub(r"[^a-z0-9]+", "", business_name.lower().split(" qa-")[0])[:28]
    return f"purchasing.{_rand(4).lower()}@{slug or 'qacustomer'}.example.com"


def slugify(text: str) -> str:
    """URL-safe slug for a product/category `slug` field (spaces -> hyphens)."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")
