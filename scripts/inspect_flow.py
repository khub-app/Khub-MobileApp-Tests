"""Robust scripted UI walker for authoring Sale Order / Fulfillment locators.

Uses explicit waits (not fixed sleeps) so it survives a slow emulator.
Dumps page_source + screenshot after each labelled stop into
scripts/_inspect/. A failed step still dumps and the walk continues.

Usage:
    venv\\Scripts\\python.exe scripts/inspect_flow.py <phase>
      phase = sale        (default) create+pay an online sale, capture order
              fulfil       assign / pick / pack the order in TD["order_no"]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from appium.webdriver.common.appiumby import AppiumBy  # noqa: E402
from selenium.webdriver.support.ui import WebDriverWait  # noqa: E402

from utilities.driver_manager import DriverManager  # noqa: E402
from pages.login_page import LoginPage  # noqa: E402

OUT = Path(__file__).resolve().parent / "_inspect"
OUT.mkdir(exist_ok=True)
TD_PATH = Path(r"C:\Users\mzees\AppData\Local\Temp\claude\c--Users-mzees-KhubAutomation-khub-mobileApp-tests\77f5ceb9-5b41-44c2-bb76-040480e5beae\scratchpad\testdata.json")
TD = json.loads(TD_PATH.read_text())

UIA = AppiumBy.ANDROID_UIAUTOMATOR
XP = AppiumBy.XPATH
AID = AppiumBy.ACCESSIBILITY_ID


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "sale"
    mgr = DriverManager(None)
    mgr.reset_app_data()
    driver = mgr.start_driver()

    def w(timeout=30):
        return WebDriverWait(driver, timeout, poll_frequency=0.5)

    def present(by, sel):
        driver.implicitly_wait(0)
        try:
            return driver.find_elements(by, sel)
        finally:
            driver.implicitly_wait(0)

    def d(name):
        (OUT / f"{name}.xml").write_text(driver.page_source, encoding="utf-8")
        driver.save_screenshot(str(OUT / f"{name}.png"))
        print(f"  [dump] {name}", flush=True)

    def tap(by, sel, note="", timeout=30):
        el = w(timeout).until(lambda dr: next(iter(dr.find_elements(by, sel)), None))
        el.click()
        print(f"  tapped {note or sel}", flush=True)

    def type_into(by, sel, text, clear=False, timeout=30):
        el = w(timeout).until(lambda dr: next(iter(dr.find_elements(by, sel)), None))
        el.click()
        if clear:
            el.clear()
        el.send_keys(text)
        print(f"  typed {text!r}", flush=True)

    def desc(text):
        return (UIA, f'new UiSelector().descriptionContains("{text}")')

    def swipe(direction="up", pct=0.6):
        size = driver.get_window_size()
        driver.execute_script("mobile: swipeGesture", {
            "left": int(size["width"] * 0.3), "top": int(size["height"] * 0.25),
            "width": int(size["width"] * 0.4), "height": int(size["height"] * 0.5),
            "direction": direction, "percent": pct, "speed": 3000})

    def swipe_to(by, sel, n=10, direction="up"):
        for _ in range(n):
            if present(by, sel):
                return
            swipe(direction, 0.55)
            time.sleep(0.6)

    def hide_kb():
        try:
            driver.hide_keyboard()
        except Exception:
            pass

    cust = TD["customer"]["name"]
    products = TD["products"]
    qtys = [2, 1, 3, 1, 2]

    try:
        lp = LoginPage(driver)
        lp.login("preprod", "Password@123")
        assert lp.is_login_successful(timeout=120), "login failed"
        print("  login OK", flush=True)
        time.sleep(3)

        if phase == "sale":
            run_sale(driver, d, tap, type_into, desc, swipe, swipe_to, hide_kb, w, cust, products, qtys)
        elif phase == "fulfil":
            run_fulfil(driver, d, tap, type_into, desc, swipe, swipe_to, hide_kb, w)
    finally:
        mgr.stop_driver()


def run_sale(driver, d, tap, type_into, desc, swipe, swipe_to, hide_kb, w, cust, products, qtys):
    tap(UIA, 'new UiSelector().className("android.view.View").clickable(true).instance(0)', "hamburger")
    tap(AID, "Sales History", "Sales History")
    time.sleep(2)
    tap(XP, '//android.widget.Button[not(@content-desc)]', "FAB")
    d("f01_cso"); time.sleep(1)

    type_into(XP, '(//android.widget.EditText)[1]', cust)
    time.sleep(3)
    d("f02_cust_results")
    tap(*desc(cust), note="cust result")
    hide_kb(); time.sleep(1)
    d("f03_cust_selected")

    tap(UIA, 'new UiSelector().description("Offsite")', "order type")
    time.sleep(1); d("f04_ordertype_open")
    tap(UIA, 'new UiSelector().description("Online")', "Online")
    time.sleep(1); d("f05_online")

    swipe_to(XP, '//android.widget.EditText[@hint="Notes (Internal)"]')
    type_into(XP, '//android.widget.EditText[@hint="Notes (Internal)"]', "AUTO-INT-NOTE-QA")
    hide_kb()
    swipe_to(XP, '//android.widget.EditText[@hint="Notes (Print on Invoice)"]')
    type_into(XP, '//android.widget.EditText[@hint="Notes (Print on Invoice)"]', "AUTO-INV-NOTE-QA")
    hide_kb(); d("f06_notes")

    swipe_to(XP, '//android.widget.Button[@content-desc="Next"]')
    tap(AID, "Next", "Next")
    time.sleep(3); d("f07_product_page")

    for i, p in enumerate(products):
        type_into(XP, '(//android.widget.EditText)[1]', p["sku"], clear=True)
        time.sleep(3)
        if i == 0:
            d("f08_prod_result")
        tap(*desc(p["sku"]), note=f"select {p['sku']}")
        hide_kb(); time.sleep(1)
        # set qty on the selection popup (2nd EditText)
        try:
            type_into(XP, '(//android.widget.EditText)[2]', str(qtys[i]), clear=True)
            hide_kb()
        except Exception as e:
            print(f"  qty set failed for {p['sku']}: {e}", flush=True)
        if i == 0:
            d("f09_prod_selected")
        tap(AID, "Add To Cart", "Add To Cart")
        time.sleep(2)
    hide_kb()
    d("f10_cart")

    swipe_to(XP, '//android.widget.Button[@content-desc="Next"]')
    tap(AID, "Next", "Next to summary")
    time.sleep(3); d("f11_cart_summary")
    for k in range(4):
        swipe("up", 0.7); time.sleep(0.5)
    d("f12_summary_bottom")

    tap(UIA, 'new UiSelector().descriptionContains("CHECKOUT")', "checkout")
    time.sleep(3); d("f13_payment")

    tap(UIA, 'new UiSelector().description("Cash")', "Cash")
    time.sleep(2); d("f14_cash_selected")
    for k in range(3):
        swipe("up", 0.6); time.sleep(0.4)
    d("f15_payment_scrolled")

    tap(UIA, 'new UiSelector().descriptionContains("Complete Sale")', "Complete Sale")
    time.sleep(5); d("f16_success_dialog")

    # OK on the success dialog
    for label in ("OK", "Ok", "Okay", "Done"):
        if driver.find_elements(UIA, f'new UiSelector().description("{label}")'):
            driver.find_element(UIA, f'new UiSelector().description("{label}")').click()
            print(f"  tapped {label}", flush=True)
            break
    time.sleep(5); d("f17_after_ok")
    for k in range(3):
        swipe("down", 0.9); time.sleep(0.3)
    d("f18_sales_history_top")


def _try(fn, label):
    try:
        fn()
        print(f"  ok: {label}", flush=True)
        return True
    except Exception as e:
        print(f"  !! {label}: {type(e).__name__}: {str(e)[:160]}", flush=True)
        return False


def run_fulfil(driver, d, tap, type_into, desc, swipe, swipe_to, hide_kb, w):
    order_no = TD.get("order_no")
    print(f"  fulfilling {order_no}", flush=True)

    def tap_any(labels, note):
        for lb in labels:
            els = driver.find_elements(UIA, f'new UiSelector().descriptionContains("{lb}")')
            if els:
                els[0].click()
                print(f"  tapped {lb} ({note})", flush=True)
                return lb
        print(f"  !! none of {labels} present ({note})", flush=True)
        return None

    tap(UIA, 'new UiSelector().className("android.view.View").clickable(true).instance(0)', "hamburger")
    tap(AID, "Fulfillment", "Fulfillment")
    time.sleep(5); d("g01_fulfillment")

    # assign  (our order is the newest -> card #1 in Pending)
    _try(lambda: tap(*desc(order_no), note="order card"), "open order card")
    time.sleep(3); d("g02_assign_dialog")
    tap_any(["Assign to Me", "Assign To Me", "Assign"], "assign")
    time.sleep(4); d("g03_assign_result")
    tap_any(["OK", "Ok", "Done"], "assign ok")
    time.sleep(3); d("g04_after_assign")

    # pick
    _try(lambda: (swipe_to(*desc(order_no)), tap(*desc(order_no), note="order card 2")), "reopen order card")
    time.sleep(3); d("g05_picking_page")
    tap_any(["Start Picking"], "start picking")
    time.sleep(4); d("g06_after_start_picking")
    tap_any(["OK", "Ok", "Done"], "picking status ok")
    time.sleep(3); d("g07_picking_list")
    for k in range(4):
        swipe("up", 0.6); time.sleep(0.4)
    d("g08_picking_bottom")
    tap_any(["Skip Scan Pick All", "Skip Scan"], "skip scan pick")
    time.sleep(3); d("g09_pick_confirm1")
    tap_any(["Yes", "Continue"], "pick confirm 1")
    time.sleep(3); d("g10_pick_confirm2")
    tap_any(["Yes", "Confirm", "Confirm Picking", "OK", "Pick", "Done"], "pick confirm 2")
    time.sleep(5); d("g11_after_pick")

    # pack
    for k in range(4):
        swipe("up", 0.6); time.sleep(0.4)
    d("g12_pack_page")
    tap_any(["Start Packing"], "start packing")
    time.sleep(4); d("g13_packing_page")
    for k in range(4):
        swipe("up", 0.6); time.sleep(0.4)
    d("g14_packing_bottom")
    tap_any(["Skip Scan Pack All", "Skip Scan"], "skip scan pack")
    time.sleep(3); d("g15_pack_confirm1")
    tap_any(["Yes", "Continue"], "pack confirm 1")
    time.sleep(3); d("g16_pack_confirm2")
    tap_any(["Yes", "Confirm", "Confirm Packing", "OK", "Pack", "Done"], "pack confirm 2")
    time.sleep(5); d("g17_pack_success")
    tap_any(["OK", "Ok", "Done"], "pack success ok")
    time.sleep(3); d("g18_after_pack")

    # packed tab
    tap(UIA, 'new UiSelector().className("android.view.View").clickable(true).instance(0)', "hamburger")
    tap(AID, "Fulfillment", "Fulfillment")
    time.sleep(3)
    tap_any(["Packed ("], "packed tab")
    time.sleep(4); d("g19_packed_tab")
    _try(lambda: swipe_to(*desc(order_no)), "find in packed")
    d("g20_packed_order")


if __name__ == "__main__":
    main()
