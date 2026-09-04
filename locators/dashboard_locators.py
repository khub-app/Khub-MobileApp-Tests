from appium.webdriver.common.appiumby import AppiumBy


class DashboardLocators:
    """Home/Dashboard screen shown immediately after a successful login."""

    TITLE = (AppiumBy.ACCESSIBILITY_ID, "Dashboard")
    TOTAL_SALE_CARD = (AppiumBy.ACCESSIBILITY_ID, "Total Sale/Revenue")

    # Bottom tab bar - each tab's content-desc is "<name>\nTab N of 6", so
    # match on a substring rather than the full string.
    TAB_HOME = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionStartsWith("Home\nTab")')
    TAB_FULFILLMENT = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionStartsWith("Fulfillment\nTab")')
    TAB_SALES = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionStartsWith("Sales\nTab")')
    TAB_CUSTOMERS = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionStartsWith("Customers\nTab")')
    TAB_PROFILE = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionStartsWith("Profile\nTab")')
    TAB_SCAN = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionStartsWith("Scan\nTab")')

    # The header hamburger has no id / content-desc - it is the first
    # clickable View in the app (confirmed live 2026-09-03; the earlier
    # Button-based selector never matched this RN build).
    HAMBURGER_MENU = (AppiumBy.ANDROID_UIAUTOMATOR,
                      'new UiSelector().className("android.view.View").clickable(true).instance(0)')
