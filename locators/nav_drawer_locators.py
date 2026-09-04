from appium.webdriver.common.appiumby import AppiumBy


class NavDrawerLocators:
    """Left navigation drawer, opened by the hamburger button in the header.

    Captured live 2026-09-03. The header hamburger has no id/desc - it is the
    first clickable View in the app. Drawer items carry a `content-desc`.
    """

    HAMBURGER = (AppiumBy.ANDROID_UIAUTOMATOR,
                 'new UiSelector().className("android.view.View").clickable(true).instance(0)')

    HOME = (AppiumBy.ACCESSIBILITY_ID, "Home")
    FULFILLMENT = (AppiumBy.ACCESSIBILITY_ID, "Fulfillment")
    SALES_HISTORY = (AppiumBy.ACCESSIBILITY_ID, "Sales History")
    CUSTOMERS = (AppiumBy.ACCESSIBILITY_ID, "Customers")
    PROFILE = (AppiumBy.ACCESSIBILITY_ID, "Profile")
    SALES_RETURN = (AppiumBy.ACCESSIBILITY_ID, "Sales Return")
    PRODUCTS = (AppiumBy.ACCESSIBILITY_ID, "Products")
