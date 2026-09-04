from appium.webdriver.common.appiumby import AppiumBy

UIA = AppiumBy.ANDROID_UIAUTOMATOR
XP = AppiumBy.XPATH
AID = AppiumBy.ACCESSIBILITY_ID


class CartSummaryLocators:
    """Cart Summary screen. Captured live 2026-09-03. Each summary row is a
    label View followed by a value View, both with their own content-desc."""

    TITLE = (AID, "Cart Summary")
    PROCEED_TO_CHECKOUT = (UIA, 'new UiSelector().descriptionContains("CHECKOUT")')
    ADDITIONAL_DISCOUNT_FIELD = (XP, '//android.widget.EditText[@hint="Additional Discount"]')
    GRAND_TOTAL_LABEL = (AID, "Grand Total")
