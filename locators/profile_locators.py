from appium.webdriver.common.appiumby import AppiumBy

AID = AppiumBy.ACCESSIBILITY_ID


class ProfileLocators:
    """Profile screen, reached via the bottom tab bar. Captured live
    2026-11-12 - flat menu items: Account Information, Products,
    Notifications, Daily Summary Report, Scan to Price Check,
    Label Management, Purchase Orders, Stocks, Contact KHUB,
    Terms & Conditions, Logout."""

    TITLE = (AID, "Profile")
    LABEL_MANAGEMENT = (AID, "Label Management")
