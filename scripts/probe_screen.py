"""Ad-hoc: log in, walk to a target area, dump each screen. For filling in
locators the main inspect_flow walk hasn't reached yet.

    venv\\Scripts\\python.exe scripts/probe_screen.py viewdetails
    venv\\Scripts\\python.exe scripts/probe_screen.py packing <SO-number>

Run ONLY when no test / other Appium session is active.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from appium.webdriver.common.appiumby import AppiumBy  # noqa: E402

from pages.login_page import LoginPage  # noqa: E402
from utilities.driver_manager import DriverManager  # noqa: E402

OUT = Path(__file__).resolve().parent / "_inspect"
UIA, XP, AID = AppiumBy.ANDROID_UIAUTOMATOR, AppiumBy.XPATH, AppiumBy.ACCESSIBILITY_ID


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "viewdetails"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    mgr = DriverManager(None)
    mgr.reset_app_data()
    dr = mgr.start_driver()

    def d(t):
        (OUT / f"{t}.xml").write_text(dr.page_source, encoding="utf-8")
        dr.save_screenshot(str(OUT / f"{t}.png"))
        print("dump", t, flush=True)

    def swipe(direction="up"):
        s = dr.get_window_size()
        dr.execute_script("mobile: swipeGesture", {
            "left": int(s["width"] * .3), "top": int(s["height"] * .25),
            "width": int(s["width"] * .4), "height": int(s["height"] * .5),
            "direction": direction, "percent": 0.7, "speed": 3000})

    try:
        lp = LoginPage(dr)
        lp.login("preprod", "Password@123")
        assert lp.is_login_successful(120), "login"
        print("login ok", flush=True)
        time.sleep(3)
        dr.find_element(UIA, 'new UiSelector().className("android.view.View").clickable(true).instance(0)').click()
        time.sleep(2)

        if what == "viewdetails":
            dr.find_element(AID, "Sales History").click()
            time.sleep(5)
            d("p_sh")
            dr.find_element(UIA, 'new UiSelector().description("Show menu")').click()
            time.sleep(2)
            d("p_actions_menu")
            for lbl in ("View Details", "View Detail", "View Order", "Details", "View"):
                els = dr.find_elements(UIA, f'new UiSelector().descriptionContains("{lbl}")')
                if els:
                    print("menu item:", lbl, flush=True)
                    els[0].click()
                    break
            time.sleep(5)
            for i in range(7):
                d(f"p_details_{i}")
                swipe("up")
                time.sleep(0.6)

        elif what == "packing":
            dr.find_element(AID, "Fulfillment").click()
            time.sleep(4)
            d("p_ful")
            # tabs: try each
            for tab in ("Picking Paused", "Picked", "Packing"):
                els = dr.find_elements(UIA, f'new UiSelector().descriptionStartsWith("{tab}")')
                if els:
                    els[0].click()
                    time.sleep(3)
                    d(f"p_tab_{tab.replace(' ', '_')}")
    finally:
        mgr.stop_driver()


if __name__ == "__main__":
    main()
