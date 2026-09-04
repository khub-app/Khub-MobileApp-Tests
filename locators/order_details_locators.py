from appium.webdriver.common.appiumby import AppiumBy

UIA = AppiumBy.ANDROID_UIAUTOMATOR
XP = AppiumBy.XPATH
AID = AppiumBy.ACCESSIBILITY_ID


class OrderDetailsLocators:
    """Order Details screen reached from Sales History -> Actions -> View
    Details. Locators are best-effort (screen not yet fully captured live);
    OrderDetailsPage reads the whole screen's content-descs and matches by
    label so it tolerates layout differences."""

    # A back chevron in the header (first clickable View / Button).
    BACK = (UIA, 'new UiSelector().className("android.widget.Button").instance(0)')

    @staticmethod
    def value_after(label: str):
        return (XP, f'(//*[@content-desc="{label}"])[1]/following-sibling::*[1]')

    @staticmethod
    def contains(text: str):
        return (UIA, f'new UiSelector().descriptionContains("{text}")')
