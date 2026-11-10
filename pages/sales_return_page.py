from locators.sales_return_locators import SalesReturnLocators as L
from pages.base_page import BasePage
from utilities.logger import get_logger

logger = get_logger(__name__)


class SalesReturnPage(BasePage):
    """Sales Return screen, reached via DashboardPage.go_to_sales_return().

    Confirmed live 2026-11-10: this screen is a READ-ONLY log of already-
    completed returns (cards carry "Return Number RE-..." / "Invoice Total"
    / "Business Name" etc. in their content-desc, same flattened-View shape
    as every other list here) - there is no FAB and no other control on it
    to START a new return. Exhaustively checked for a return-creation entry
    point elsewhere too: a Sales History order card's "Show menu" (Pending
    AND Packed orders) offers only View Details/Print Invoice/Send Email,
    and Order Details' own tabs (Order Detail/Payment History) have nothing
    either.

    The web portal's equivalent action (Sales History row's "..." menu ->
    "Return") only appears once an order's Order Status reaches
    **Completed** - a status this project has never driven an order to
    (Fulfillment here only goes Pending -> ... -> Packed; reaching
    Completed needs the separate, unexplored Delivery & Shipping
    execute/deliver flow). So before a mobile return-CREATION test is
    possible, that prerequisite flow needs automating first - this page
    object is deliberately left as read-only/log parsing for now rather
    than guessing at a creation flow that may not even exist on mobile."""

    def is_loaded(self, timeout: int = 20) -> bool:
        return self.is_displayed(L.TITLE, timeout)
