import os
import shutil
import subprocess
import time

from appium.webdriver.common.appiumby import AppiumBy

from config.config_reader import ConfigReader
from pages.base_page import BasePage
from utilities.logger import get_logger

logger = get_logger(__name__)

ADMIN_APP_PACKAGE = "com.esolutions.demotaxadmin"

# Chrome's own one-time first-run screen ("Welcome to Chrome... Sign in to
# browse easier across devices"). `pm clear` only clears the ADMIN app's
# data between test classes, never Chrome's, so this only appears on a
# genuinely fresh emulator/device - confirmed live 2026-11-13.
_CHROME_FIRST_RUN_LABELS = ("Use without an account", "No thanks", "Got it", "OK", "Accept & continue")


class PrintInvoicePage(BasePage):
    """Sales History's Actions -> "Print Invoice" does NOT open a screen
    inside the admin app - it opens the invoice as a real web page in the
    device's own Chrome browser. Confirmed live 2026-11-13:
    `driver.current_package` becomes `com.android.chrome`, a separate task
    with its own full browser chrome (URL bar, back/forward, menu) - not a
    Custom Tab embedded in the app's own task.

    Each product line on the invoice shows its Label Management label (the
    one shown as a "Labels:" chip on the active Picking list) as a colored
    chip directly under the product name - confirmed live with an exact
    text match against the label name. Getting there from a fresh Chrome
    needs two things neither native screen in this app needs:
      - dismissing Chrome's own first-run screen first (see above).
      - scrolling the page down at least once - Chrome's accessibility
        bridge only exposes the product table's text once it has been
        rendered/scrolled into view, confirmed live (0 scrolls: not found;
        1 scroll: found).
    """

    def _dismiss_chrome_first_run(self):
        for label in _CHROME_FIRST_RUN_LABELS:
            els = self.driver.find_elements(
                AppiumBy.XPATH, f'//*[@text="{label}" or @content-desc="{label}"]')
            if els:
                logger.info(f"Dismissing Chrome's first-run screen: '{label}'")
                els[0].click()
                time.sleep(2)

    def _adb_dump(self) -> str:
        """Raw accessibility-tree dump via `adb exec-out uiautomator dump`.

        Confirmed live 2026-11-13: `driver.page_source` (Appium's own
        UiAutomator2 snapshot) can keep missing text that is already
        visibly rendered on this Chrome-hosted invoice page - confirmed by
        polling it for 90s straight without success while a screenshot
        taken moments later clearly showed the label - whereas a plain
        `adb` dump taken around the same time finds it immediately. Root
        cause not pinned down (this page's deep web DOM is the main
        suspect for tripping some size/depth limit in Appium's own
        snapshot), but the adb dump is the reliable source of truth here,
        so `contains_text` checks both."""
        adb = shutil.which("adb") or ("adb.exe" if os.name == "nt" else "adb")
        cmd = [adb]
        udid = ConfigReader().get_environment().get("udid")
        if udid:
            cmd += ["-s", udid]
        cmd += ["exec-out", "uiautomator", "dump", "/dev/tty"]
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout
        except Exception as e:
            logger.debug(f"adb uiautomator dump failed: {e}")
            return ""

    def contains_text(self, text: str) -> bool:
        if text in self.driver.page_source:
            return True
        return text in self._adb_dump()

    def scroll_until_visible(self, expect_text: str, max_scrolls: int = 10, settle_timeout: int = 30) -> bool:
        """Dismiss Chrome's first-run screen if present, then scroll the
        invoice page down until `expect_text` appears in the page source
        (or give up after `max_scrolls` + `settle_timeout` seconds).
        Returns whether it was found.

        Confirmed live 2026-11-13: once scrolling reaches the bottom,
        further identical swipes don't change anything, but how long Chrome's
        accessibility bridge then takes to expose the newly-rendered text
        varies a lot run to run - seen resolving within ~15s on one run, and
        needing closer to a minute on another (manually confirmed present via
        `adb exec-out uiautomator dump` well after a timed-out run had
        already failed) - this is a render-settle delay, not a scroll
        problem, so once the scroll loop is exhausted this keeps polling
        (no further scrolling) for up to `settle_timeout` seconds rather
        than giving up after only a few quick retries."""
        self._dismiss_chrome_first_run()
        size = self.driver.get_window_size()
        for _ in range(max_scrolls):
            if self.contains_text(expect_text):
                return True
            self.driver.swipe(
                size["width"] // 2, int(size["height"] * 0.85),
                size["width"] // 2, int(size["height"] * 0.2), 400)
            time.sleep(1)
        deadline = time.time() + settle_timeout
        while time.time() < deadline:
            if self.contains_text(expect_text):
                return True
            time.sleep(2)
        return self.contains_text(expect_text)

    def close_and_return_to_app(self):
        """Bring the admin app back to the foreground. Print Invoice opens
        a SEPARATE Chrome task (not a Custom Tab inside the app's own
        task), so a plain Android back press would stay inside Chrome's
        own history instead of returning to the app - confirmed live that
        `activate_app` correctly resumes the admin app exactly where it
        was (e.g. still on Sales History, same order still in the list),
        rather than restarting it."""
        from pages.sales_history_page import SalesHistoryPage

        logger.info("Returning to the admin app from Chrome")
        self.driver.activate_app(ADMIN_APP_PACKAGE)
        time.sleep(1)
        return SalesHistoryPage(self.driver)
