from appium.webdriver.common.appiumby import AppiumBy


class LoginLocators:
    """Locators captured live from the Khub PreProd Admin app
    (com.esolutions.demotaxadmin) on a cleared-data fresh install.

    The RN devs set no testID / nativeID / accessibilityLabel on the two text
    inputs, so they're addressed positionally by EditText index. The header
    text and the Login button DO carry content-desc values.
    """

    # Email/Username is the 1st EditText on screen, Password the 2nd.
    USERNAME_INPUT = (AppiumBy.ANDROID_UIAUTOMATOR,
                      'new UiSelector().className("android.widget.EditText").instance(0)')
    PASSWORD_INPUT = (AppiumBy.ANDROID_UIAUTOMATOR,
                      'new UiSelector().className("android.widget.EditText").instance(1)')

    LOGIN_BUTTON = (AppiumBy.ACCESSIBILITY_ID, "Login")           # content-desc="Login"
    FORGOT_PASSWORD = (AppiumBy.ACCESSIBILITY_ID, "Forgot Password?")

    # Login-screen-only markers
    WELCOME_HEADER = (AppiumBy.ACCESSIBILITY_ID, "KHub PreProd Admin")
    EMAIL_REQUIRED_ERROR = (AppiumBy.ACCESSIBILITY_ID, "Please Enter Email Address")
    PASSWORD_REQUIRED_ERROR = (AppiumBy.ACCESSIBILITY_ID, "Please Enter Password")
