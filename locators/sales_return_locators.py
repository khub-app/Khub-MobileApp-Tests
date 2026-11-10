from appium.webdriver.common.appiumby import AppiumBy

UIA = AppiumBy.ANDROID_UIAUTOMATOR
XP = AppiumBy.XPATH
AID = AppiumBy.ACCESSIBILITY_ID


class SalesReturnLocators:
    """Sales Return screen. Locators captured live 2026-11-10 - see
    pages/sales_return_page.py for the flow this supports."""

    TITLE = (AID, "Sales Return")
