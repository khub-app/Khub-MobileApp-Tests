from appium.webdriver.common.appiumby import AppiumBy

UIA = AppiumBy.ANDROID_UIAUTOMATOR
XP = AppiumBy.XPATH
AID = AppiumBy.ACCESSIBILITY_ID


class FulfillmentLocators:
    """Fulfillment screen + the picking / packing sub-flows. Best-effort
    locators (to be confirmed live during test runs) built on the same
    "one card == one content-desc" pattern the rest of the app uses."""

    TITLE = (AID, "Fulfillment")

    # Top status tabs - the count in each label ("Pending (72)") changes.
    TAB_PENDING = (UIA, 'new UiSelector().descriptionStartsWith("Pending")')
    TAB_PACKED = (UIA, 'new UiSelector().descriptionStartsWith("Packed")')

    SEARCH_ICON = (UIA, 'new UiSelector().descriptionContains("Search")')
    SEARCH_FIELD = (XP, '(//android.widget.EditText)[1]')

    @staticmethod
    def order_card(order_no: str):
        return (UIA, f'new UiSelector().descriptionContains("{order_no}")')

    # Assign flow:
    #   bottom sheet  -> "This order not been assigned" + button "Assign to me"
    #   Info dialog    -> "Order has been assigned to the user '<user>'." + OK
    ASSIGN_DIALOG = (UIA, 'new UiSelector().descriptionContains("not been assigned")')
    ASSIGN_TO_ME = (UIA, 'new UiSelector().descriptionContains("Assign to")')
    ASSIGN_SUCCESS = (UIA, 'new UiSelector().descriptionContains("has been assigned")')

    # Picking
    ORDER_INFO = (UIA, 'new UiSelector().descriptionContains("Order Info")')
    START_PICKING = (UIA, 'new UiSelector().descriptionContains("Start Picking")')
    SKIP_SCAN_PICK_ALL = (UIA, 'new UiSelector().descriptionContains("Skip Scan Pick All")')
    COMPLETE_PICKING = (UIA, 'new UiSelector().descriptionContains("Complete Picking")')
    START_PACKING = (UIA, 'new UiSelector().descriptionContains("Start Packing")')

    # Packing
    START_PACKING2 = (UIA, 'new UiSelector().descriptionContains("Start Packing")')
    SKIP_SCAN_PACK_ALL = (UIA, 'new UiSelector().descriptionContains("Skip Scan Pack All")')
    COMPLETE_PACKING = (UIA, 'new UiSelector().descriptionContains("Complete Packing")')
    # Success dialog text: "SO-<n> has been successfully packed."
    PACKED_SUCCESS = (UIA, 'new UiSelector().descriptionContains("successfully packed")')

    # Generic dialog buttons
    YES = (UIA, 'new UiSelector().description("Yes")')
    OK = (UIA, 'new UiSelector().description("OK")')

    @staticmethod
    def button_containing(text: str):
        return (UIA, f'new UiSelector().descriptionContains("{text}")')
