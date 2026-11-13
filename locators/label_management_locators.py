from appium.webdriver.common.appiumby import AppiumBy

UIA = AppiumBy.ANDROID_UIAUTOMATOR
XP = AppiumBy.XPATH
AID = AppiumBy.ACCESSIBILITY_ID


class LabelManagementLocators:
    """Profile > Label Management, and its "+" Create Label modal.
    Captured live 2026-11-12."""

    TITLE = (AID, "Label Management")

    # The only Button on this screen (same pattern as Sales History's FAB -
    # confirmed live, no content-desc of its own).
    ADD_BUTTON = (UIA, 'new UiSelector().className("android.widget.Button")')

    @staticmethod
    def label_card(name: str):
        # Card content-desc: "<name>\nProduct Label\nStatus\nActive\n
        # Label Preview\n<name>\nFulfillment\nInvoice[\nDescription\n<desc>]"
        # Anchored on the newline after the name for the same reason as
        # this project's other list screens: a short/generic label name
        # could otherwise substring-match an unrelated card.
        return (XP, f'//*[contains(@content-desc,"{name}\nProduct Label")]')


class CreateLabelLocators:
    """The "Create Label" modal opened from LabelManagementLocators.ADD_BUTTON.
    Captured live 2026-11-12 - fields and behavior confirmed by actually
    creating a label end-to-end (success message "Tag has been saved
    successfully.", new card appears in the list)."""

    TITLE = (AID, "Create Label")

    # Label Name is always the form's first EditText; Description is
    # always its last - stable regardless of Label Type, since the
    # Fulfillment/Invoice checkboxes only appear BETWEEN them once
    # Label Type = Product is chosen.
    LABEL_NAME_FIELD = (XP, '(//android.widget.EditText)[1]')
    DESCRIPTION_FIELD = (XP, '(//android.widget.EditText)[last()]')

    # Fresh-form-only: shows "Select" until a type is chosen. Not valid for
    # editing an already-typed label (which shows "Product"/"Order" instead).
    LABEL_TYPE_DROPDOWN_UNSET = (AID, "Select")
    LABEL_TYPE_PRODUCT_OPTION = (AID, "Product")
    LABEL_TYPE_ORDER_OPTION = (AID, "Order")

    # Only rendered once Label Type = Product. Each is a plain clickable
    # View wrapping a real CheckBox child - tapping the View (not just the
    # CheckBox) toggles it, confirmed live.
    FULFILLMENT_CHECKBOX = (AID, "Fulfillment")
    INVOICE_CHECKBOX = (AID, "Invoice")

    # Fresh-form-only defaults (factory colors before any customization).
    # Fragile if reused to edit an already-customized label - this page
    # object is for the create flow only.
    BACKGROUND_COLOR_FIELD_DEFAULT = (AID, "#FFFFFF")
    TEXT_COLOR_FIELD_DEFAULT = (AID, "#000000")

    # Inside the color-picker dialog (opened by tapping either color field
    # above): a "Hex" input (type a 6-digit hex, no "#") plus a "Presets"
    # swatch grid with no accessible color values - the Hex field is the
    # only reliable way to set an EXACT color. "Apply" commits it.
    COLOR_HEX_INPUT = (XP, '//android.widget.EditText')
    COLOR_APPLY_BUTTON = (AID, "Apply")

    CREATE_TAG_BUTTON = (AID, "Create tag")

    SUCCESS_MESSAGE = (UIA, 'new UiSelector().descriptionContains("has been saved successfully")')
