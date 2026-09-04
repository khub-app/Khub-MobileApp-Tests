import os
import shutil
import subprocess
import time

from appium import webdriver
from appium.options.android import UiAutomator2Options

from config.config_reader import ConfigReader
from utilities.logger import get_logger

logger = get_logger(__name__)


class DriverManager:
    """Builds capabilities from config/config.yaml and owns the Appium session lifecycle."""

    def __init__(self, env_name: str | None = None):
        self.env_name = env_name
        self.config = ConfigReader().get_environment(env_name)
        self.driver = None

    def reset_app_data(self):
        """Clear the app's local storage via adb so every test class starts
        logged out. The admin app keeps its login session across restarts
        (noReset keeps it that way), so without this the test order would
        decide whether a test sees the Login screen or an authenticated app.
        """
        app_package = self.config.get("app_package")
        if not app_package:
            return

        adb = self._adb_path()
        cmd = [adb]
        if self.config.get("udid"):
            cmd += ["-s", self.config["udid"]]
        cmd += ["shell", "pm", "clear", app_package]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"adb pm clear failed for {app_package}: {result.stderr.strip()}")
        else:
            logger.info(f"Cleared app data for {app_package}")

        self._ensure_connectivity()

    def _adb_shell(self, *args, timeout: int = 15) -> str:
        cmd = [self._adb_path()]
        if self.config.get("udid"):
            cmd += ["-s", self.config["udid"]]
        cmd += ["shell", *args]
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
        except Exception as e:
            logger.debug(f"adb shell {' '.join(args)} failed: {e}")
            return ""

    def _default_network_validated(self) -> bool | None:
        """True/False if a default network exists and its VALIDATED state is
        known; None if adb couldn't tell us."""
        out = self._adb_shell("dumpsys", "connectivity")
        if not out:
            return None
        if "Active default network: none" in out:
            return False
        line = next((ln for ln in out.splitlines() if "Active default network:" in ln), "")
        net_id = line.split(":", 1)[1].strip() if ":" in line else ""
        # the block for that network id carries its Capabilities: ...
        block = next((b for b in out.split("NetworkAgentInfo") if f"network{{{net_id}}}" in b), "")
        if not block:
            return None
        return "VALIDATED" in block

    def _ensure_connectivity(self):
        """The Pixel_Tablet AVD's network occasionally comes up without a
        VALIDATED default (the simulated "AndroidWifi" AP fails its portal
        check), which makes the app's backend login hang for the full timeout.
        A Wi-Fi off/on cycle almost always fixes it. We only intervene when
        the default is actually non-validated - never blindly disable Wi-Fi,
        since on some boots it is the only network. Real devices are left
        alone."""
        if self.config.get("udid"):
            return
        validated = self._default_network_validated()
        if validated is True:
            return
        if validated is None:
            logger.debug("Could not read emulator connectivity; leaving it alone")
            return
        logger.warning("Emulator default network is not VALIDATED - cycling Wi-Fi")
        self._adb_shell("svc", "wifi", "disable")
        time.sleep(2)
        self._adb_shell("svc", "wifi", "enable")
        for _ in range(10):
            time.sleep(3)
            if self._default_network_validated() is True:
                logger.info("Emulator connectivity restored")
                return
        logger.warning("Emulator still has no validated network - login is likely to fail")

    @staticmethod
    def _adb_path() -> str:
        exe_name = "adb.exe" if os.name == "nt" else "adb"
        candidate_roots = [
            os.environ.get("ANDROID_HOME"),
            os.environ.get("ANDROID_SDK_ROOT"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk") if os.name == "nt" else None,
        ]
        for root in candidate_roots:
            if not root:
                continue
            candidate = os.path.join(root, "platform-tools", exe_name)
            if os.path.isfile(candidate):
                return candidate
        return shutil.which("adb") or exe_name

    def start_driver(self):
        options = UiAutomator2Options()
        options.platform_name = self.config.get("platform_name", "Android")
        options.automation_name = self.config.get("automation_name", "UiAutomator2")
        options.device_name = self.config["device_name"]
        options.app_package = self.config["app_package"]
        options.app_activity = self.config["app_activity"]
        options.no_reset = self.config.get("no_reset", True)
        options.full_reset = self.config.get("full_reset", False)
        options.new_command_timeout = self.config.get("new_command_timeout", 120)
        options.auto_grant_permissions = self.config.get("auto_grant_permissions", True)
        # React Native apps can take 15-20s+ to report their first frame drawn
        # on a loaded emulator; Appium's 20s default adbExecTimeout is too tight.
        options.set_capability("adbExecTimeout", self.config.get("adb_exec_timeout", 60000))
        # Allow switching into any WebView the admin app embeds. Also requires
        # the Appium server to be started with
        # --allow-insecure uiautomator2:chromedriver_autodownload
        options.set_capability("chromedriverAutodownload", True)

        if self.config.get("app_path"):
            options.app = self.config["app_path"]
        if self.config.get("udid"):
            options.udid = self.config["udid"]
        if self.config.get("platform_version"):
            options.platform_version = self.config["platform_version"]

        server_url = self.config.get("appium_server", "http://127.0.0.1:4723")
        logger.info(f"Starting Appium session on {server_url} (env={self.env_name or 'default'})")
        self.driver = webdriver.Remote(server_url, options=options)
        return self.driver

    def stop_driver(self):
        if self.driver is not None:
            logger.info("Quitting Appium session")
            self.driver.quit()
            self.driver = None
