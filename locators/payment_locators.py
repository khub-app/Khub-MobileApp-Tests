from appium.webdriver.common.appiumby import AppiumBy

UIA = AppiumBy.ANDROID_UIAUTOMATOR
XP = AppiumBy.XPATH
AID = AppiumBy.ACCESSIBILITY_ID


class PaymentLocators:
    """"Choose Your Payment Method" screen (last step of Create Sale Order).
    Captured live 2026-09-03."""

    HEADER = (AID, "Choose Your Payment Method")
    INVOICE_TOTAL = (XP, '//*[@content-desc="Invoice Total"]/following-sibling::*[1]')
    CUSTOMER = (XP, '//*[@content-desc="Customer"]/following-sibling::*[1]')

    CASH_MODE = (UIA, 'new UiSelector().description("Cash")')
    CHEQUE_MODE = (UIA, 'new UiSelector().description("Cheque")')
    CARD_MODE = (UIA, 'new UiSelector().description("Credit/Debit Card")')

    # Amount field shown after a payment mode is selected (first EditText).
    AMOUNT_FIELD = (XP, '(//android.widget.EditText)[1]')

    COMPLETE_SALE = (UIA, 'new UiSelector().descriptionContains("Complete Sale")')
    BACK = (UIA, 'new UiSelector().description("Back")')

    # Success dialog
    SUCCESS_MESSAGE = (UIA, 'new UiSelector().descriptionContains("saved successfully")')
    OK_BUTTON = (UIA, 'new UiSelector().description("OK")')
