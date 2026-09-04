from appium.webdriver.common.appiumby import AppiumBy


class SalesHistoryLocators:
    """Sales History list screen. Captured live 2026-09-03.

    Each order is one clickable `android.view.View` whose `content-desc` is
    every field of the card newline-joined, e.g.:
      "Sr.No\n1\nOrder Number\nSO-260903-64138\nDate / Time\n03-Sep-2026\n
       Sold By\npreprod\nOrder Type\nOnline\nInvoice Status\nPaid\nStatus\n
       Packed\nSale Total\n$ 55.75\nBusiness Name\n<name>\nActions\nTags"
    so a card is located by descriptionContains(order_no) and its fields are
    parsed out of that string (see SalesHistoryPage.get_order_card).
    """

    TITLE = (AppiumBy.ACCESSIBILITY_ID, "Sales History")
    # Pink circular FAB, bottom-right - the only Button with no content-desc.
    # It sometimes expands into a speed-dial (mini-FABs "Sale Order" / "Sale
    # Return" + a cart/refresh icon, main FAB morphs into an X to close it)
    # instead of navigating straight to Create Sale Order - SalesHistoryPage.
    # tap_create_sale_order() checks for and taps the "Sale Order" option
    # when that happens.
    CREATE_FAB = (AppiumBy.XPATH, '//android.widget.Button[not(@content-desc)]')
    FAB_SALE_ORDER_OPTION_DESC = (AppiumBy.ANDROID_UIAUTOMATOR,
                                  'new UiSelector().descriptionContains("Sale Order")')
    FAB_SALE_ORDER_OPTION_TEXT = (AppiumBy.ANDROID_UIAUTOMATOR,
                                  'new UiSelector().textContains("Sale Order")')

    @staticmethod
    def order_card(order_no: str):
        return (AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().descriptionContains("{order_no}")')

    @staticmethod
    def order_card_actions(order_no: str):
        # The "Show menu" (•••) view lives inside the matching card.
        return (AppiumBy.XPATH,
                f'//android.view.View[contains(@content-desc,"{order_no}")]'
                f'//android.view.View[@content-desc="Show menu"]')

    # Actions popup menu entries (content-desc)
    VIEW_DETAILS = (AppiumBy.ACCESSIBILITY_ID, "View Details")
