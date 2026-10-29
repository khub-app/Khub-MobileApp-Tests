from appium.webdriver.common.appiumby import AppiumBy

UIA = AppiumBy.ANDROID_UIAUTOMATOR
XP = AppiumBy.XPATH
AID = AppiumBy.ACCESSIBILITY_ID


class CreateSaleOrderLocators:
    """Create Sale Order - step 1 (customer + order info) and step 2
    (product selection). Captured live 2026-09-03."""

    TITLE = (AID, "Create Sale Order")

    # ---- step 1: customer + order info ----
    CUSTOMER_SEARCH = (XP, '(//android.widget.EditText)[1]')  # hint "Search Customer by Name"
    ADD_QUICK_CUSTOMER = (AID, "Add Quick Customer")

    @staticmethod
    def customer_result(name: str):
        return (UIA, f'new UiSelector().descriptionContains("{name}")')

    # After a customer is chosen the summary card shows these colon-suffixed
    # fields (a plain search-result row does not).
    SELECTED_CUSTOMER_MARKER = (UIA, 'new UiSelector().description("Customer Balance:")')

    # The Order Type control renders as a Button whose content-desc is the
    # current value (default "Offsite"); tapping it opens the options list.
    ORDER_TYPE_DROPDOWN = (UIA,
        'new UiSelector().className("android.widget.Button")'
        '.descriptionMatches("Walk In|Phone|Online|Offsite|Other")')

    @staticmethod
    def order_type_value(value: str):
        return (UIA, f'new UiSelector().className("android.widget.Button").description("{value}")')

    @staticmethod
    def dropdown_option(value: str):
        return (UIA, f'new UiSelector().description("{value}")')

    NOTES_INTERNAL = (XP, '//android.widget.EditText[@hint="Notes (Internal)"]')
    NOTES_INVOICE = (XP, '//android.widget.EditText[@hint="Notes (Print on Invoice)"]')

    NEXT_BUTTON = (AID, "Next")

    # ---- step 2: product selection ----
    PRODUCT_STEP_MARKER = (AID, "Add Product By Name / SKU / UPC")
    PRODUCT_SEARCH = (XP, '(//android.widget.EditText)[1]')  # hint "Search Product"
    ADDED_TO_CART_HEADER = (AID, "Added to the Cart")
    ADD_TO_CART_BUTTON = (AID, "Add To Cart")
    NOTHING_IN_CART = (AID, "Nothing in cart")

    # A UOM product (4 chained Piece/Pack/Case/Pallet tiers) shows this next
    # to a cart line already holding one tier of that product - it opens a
    # menu listing only the tiers NOT yet in the cart (by their configured
    # label, e.g. "Box"/"Carton"/"Package"), each adding a new, separate
    # cart line for that tier. Confirmed live 2026-10-29: this is the only
    # way the app exposes more than one UOM tier on an order - there is no
    # Unit selector before Add To Cart, only after.
    ADD_ANOTHER_UNIT = (AID, "Add another unit")

    @staticmethod
    def unit_option(label: str):
        return (AID, label)

    @staticmethod
    def product_result(sku: str):
        # search result row: content-desc "<name>\n<sku>\n$<price>"
        return (UIA, f'new UiSelector().descriptionContains("{sku}")')

    # qty field on the selection popup (2nd EditText; 1st is the search box)
    SELECT_QTY_FIELD = (XP, '(//android.widget.EditText)[2]')

    @staticmethod
    def cart_line(sku: str, upc: str | None = None):
        # cart line View: content-desc contains "<name>\n<cat>\n<sku>/<upc>\n
        # Qty: <avail>\nPrice *\nSale Price:$<p>\nOrder Qty *\nSub Total\n
        # $<sub>\nUnit *\nTotal: $<sub>"
        # A UOM product's 4 tiers share one SKU, so "{sku}/" alone matches
        # all of them - pass `upc` (unique per tier) to target exactly one.
        desc = f"{sku}/{upc}" if upc else f"{sku}/"
        return (UIA, f'new UiSelector().descriptionContains("{desc}")')

    @staticmethod
    def cart_line_price_field(sku: str, upc: str | None = None):
        desc = f"{sku}/{upc}" if upc else f"{sku}/"
        return (XP,
                f'//android.view.View[contains(@content-desc,"{desc}")]'
                f'//android.widget.EditText[1]')

    @staticmethod
    def cart_line_qty_field(sku: str, upc: str | None = None):
        desc = f"{sku}/{upc}" if upc else f"{sku}/"
        return (XP,
                f'//android.view.View[contains(@content-desc,"{desc}")]'
                f'//android.widget.EditText[2]')
