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

    @staticmethod
    def product_result(sku: str):
        # search result row: content-desc "<name>\n<sku>\n$<price>"
        return (UIA, f'new UiSelector().descriptionContains("{sku}")')

    # qty field on the selection popup (2nd EditText; 1st is the search box)
    SELECT_QTY_FIELD = (XP, '(//android.widget.EditText)[2]')

    @staticmethod
    def cart_line(sku: str):
        # cart line View: content-desc contains "<name>\n<cat>\n<sku>/<upc>\n
        # Qty: <avail>\nPrice *\nSale Price:$<p>\nOrder Qty *\nSub Total\n
        # $<sub>\nUnit *\nTotal: $<sub>"
        return (UIA, f'new UiSelector().descriptionContains("{sku}/")')

    @staticmethod
    def cart_line_price_field(sku: str):
        return (XP,
                f'//android.view.View[contains(@content-desc,"{sku}/")]'
                f'//android.widget.EditText[1]')

    @staticmethod
    def cart_line_qty_field(sku: str):
        return (XP,
                f'//android.view.View[contains(@content-desc,"{sku}/")]'
                f'//android.widget.EditText[2]')
