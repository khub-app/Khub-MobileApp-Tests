from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utilities.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TIMEOUT = 60  # host CPU contention can slow instrumentation/render well past 30s
POLL_FREQUENCY = 0.5


class WaitHelper:
    """Explicit-wait wrapper. No hard-coded sleeps anywhere in the framework."""

    def __init__(self, driver, timeout: int = DEFAULT_TIMEOUT):
        self.driver = driver
        self.timeout = timeout

    def _wait(self, timeout=None):
        return WebDriverWait(
            self.driver, timeout or self.timeout, poll_frequency=POLL_FREQUENCY,
            ignored_exceptions=(StaleElementReferenceException,),
        )

    def wait_for_visible(self, locator, timeout=None):
        try:
            return self._wait(timeout).until(EC.visibility_of_element_located(locator))
        except TimeoutException:
            logger.error(f"Element not visible within {timeout or self.timeout}s: {locator}")
            raise

    def wait_for_clickable(self, locator, timeout=None):
        try:
            return self._wait(timeout).until(EC.element_to_be_clickable(locator))
        except TimeoutException:
            logger.error(f"Element not clickable within {timeout or self.timeout}s: {locator}")
            raise

    def wait_for_gone(self, locator, timeout=None):
        try:
            return self._wait(timeout).until(EC.invisibility_of_element_located(locator))
        except TimeoutException:
            logger.error(f"Element still present after {timeout or self.timeout}s: {locator}")
            raise

    def wait_for_all_visible(self, locator, timeout=None):
        try:
            return self._wait(timeout).until(EC.visibility_of_all_elements_located(locator))
        except TimeoutException:
            logger.error(f"Elements not all visible within {timeout or self.timeout}s: {locator}")
            raise
