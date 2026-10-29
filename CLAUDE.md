# khub-mobileApp-tests — Project Guide for Claude

Loaded automatically at the start of every session. Read it fully before making changes.

---

## What This Project Is

End-to-end automation for the **Khub PreProd Admin** Android app
(`com.esolutions.demotaxadmin`) — a React Native business-management app
(Dashboard, Fulfillment, Sales, Customers, Profile, Scan). Built with
**Python + Appium + pytest**.

Sibling projects under `C:\Users\mzees\KhubAutomation\`:

| Repo | Surface | Framework |
|------|---------|-----------|
| khub-web-tests | Web (Chromium) | Playwright |
| khub-pos-tests | Android POS tablet app (`com.anonymous.ititansapp`) | Appium + uiautomator2 |
| **khub-mobileApp-tests** | Android Admin app (`com.esolutions.demotaxadmin`) | Appium + uiautomator2 |

This project's framework is a deliberate mirror of **khub-pos-tests** — same
Page Object / locators split, same `DriverManager` / `WaitHelper` / conftest
patterns. When in doubt, check how khub-pos-tests does it.

All three suites run against the shared **preprod** tenant
(`https://preprod.ikhub.biz`, login `preprod` / `Password@123`).

---

## Tech Stack

| Component | Detail |
|-----------|--------|
| Python | 3.12 (`venv/`) |
| Appium | 3.6.x (global npm) |
| Driver | uiautomator2 8.x |
| Appium-Python-Client | 5.3.1 |
| pytest | 9.1.1 |
| Emulator AVD | `Pixel_Tablet` (API 35 / Android 15) — the only AVD installed |
| Java | JDK 17 (`JAVA_HOME`) |
| Android SDK | `ANDROID_HOME=C:\Users\mzees\AppData\Local\Android\Sdk`, build-tools 36.0.0 |

The admin APK targets SDK 36 but `minSdk` is 24, so it installs and runs fine
on the API-35 `Pixel_Tablet` AVD.

---

## Prerequisites — Must Be Running Before Tests

1. **Android emulator** booted:
   `& "$env:ANDROID_HOME\emulator\emulator.exe" -avd Pixel_Tablet`
2. **Appium server** at `http://127.0.0.1:4723`: `appium`
   (for any embedded WebView flow, start it with
   `appium --allow-insecure uiautomator2:chromedriver_autodownload`)
3. **APK installed**: `adb install -r -g data\apk\preprod-admin.apk`
   (the build lives at `data/apk/preprod-admin.apk`; also kept a copy at the
   repo root as `preprod-admin-030926.apk`. Both are gitignored.)

`DriverManager.reset_app_data()` runs `adb shell pm clear
com.esolutions.demotaxadmin` before every test class, so each class starts
logged out on the Login screen.

---

## How to Run

Preferred (mirrors khub-pos-tests) — reads `data/test_data.xlsx` `RunConfig`
sheet for environment + Smoke/Regression toggle, `Tags` sheet for which markers
each file gets:

```
.\run_mobile_tests.ps1
.\run_mobile_tests.ps1 -Path tests/login -Suite ""     # a folder, no marker filter
.\run_mobile_tests.ps1 -Env real_device
```

Direct pytest (bypass the sheet):

```
venv\Scripts\python.exe -m pytest tests/ -v
venv\Scripts\python.exe -m pytest tests/login/ -v
venv\Scripts\python.exe -m pytest tests/ -v -m smoke
venv\Scripts\python.exe -m pytest tests/ -v --env=real_device
```

Full command reference: **COMMANDS.md**.

The Allure HTML report is regenerated automatically after every run
(`conftest.py` `pytest_sessionfinish`) → `reports/allure-report/index.html`.
Requires the `allure` CLI on PATH; without it the run still passes and prints
the manual `allure generate` command.

---

## Project Structure

```
khub-mobileApp-tests/
├── config/
│   ├── config.yaml          # Appium caps + environments (emulator / real_device)
│   └── config_reader.py     # loads config.yaml, resolves active env (MOBILE_ENV / --env)
├── data/
│   ├── test_data.yaml       # credentials + test inputs
│   ├── test_data.xlsx       # RunConfig + Tags + TestConfigs sheets (mirrors khub-pos-tests)
│   └── apk/preprod-admin.apk
├── locators/                # AppiumBy tuples only, one file per screen
│   ├── login_locators.py
│   └── dashboard_locators.py
├── pages/                   # page objects, all inherit BasePage
│   ├── base_page.py
│   ├── login_page.py
│   └── dashboard_page.py
├── tests/
│   ├── base_test.py         # BaseTest — exposes the class-scoped `driver` fixture as self.driver
│   └── login/test_login.py
├── utilities/
│   ├── driver_manager.py    # builds caps, owns the Appium session, pm clear
│   ├── wait_helper.py       # explicit waits — NO time.sleep in framework code
│   ├── logger.py
│   ├── screenshot_helper.py
│   └── report_metadata.py   # Allure environment.properties / executor.json
├── scripts/
│   ├── inspect_app.py       # launch the app + dump page_source/screenshot for locator work
│   ├── gen_test_data_xlsx.py# rebuilds data/test_data.xlsx (edit here, not the binary)
│   └── read_run_config.py   # run_mobile_tests.ps1 reads RunConfig sheet via this
├── run_mobile_tests.ps1            # RunConfig-sheet-driven runner (Environment + Smoke/Regression)
├── COMMANDS.md              # command reference (emulator / Appium / run / APK)
├── conftest.py              # driver fixture, Excel Tags markers, per-step screenshots, fail-fast, Allure gen
├── pytest.ini
└── requirements.txt
```

---

## Locator Notes (captured live 2026-09-03, APK versionName 1.0.3 / versionCode 9)

This app sets **no `testID` / `nativeID` / `accessibilityLabel`** on its text
inputs. What IS available:

- **Login username / password**: no id — addressed positionally as the 1st and
  2nd `android.widget.EditText` (`UiSelector().className(...).instance(0|1)`).
- **Login button**: `content-desc="Login"` → `ACCESSIBILITY_ID`.
- **Header**: `content-desc="KHub PreProd Admin"`.
- **Validation errors**: `content-desc="Please Enter Email Address"` /
  `"Please Enter Password"`.
- **Dashboard**: `content-desc="Dashboard"`, card `"Total Sale/Revenue"`.
- **Bottom tabs**: `content-desc="<Name>\nTab N of 6"` (Home, Fulfillment,
  Sales, Customers, Profile, Scan) — match with `descriptionStartsWith`.

### Gotchas found live
- **RN TextInputs need focus before `send_keys`.** An unfocused `send_keys` is
  silently dropped and the form submits with "Please Enter ..." errors.
  `BasePage.type_text` taps the element first — keep it that way.
- **Login is slow.** The backend round-trip on a loaded emulator takes 30s+;
  `is_login_successful()` waits up to 60s (90s in `MobileBaseSetup`).
- **Emulator connectivity flakes → login hangs.** The `Pixel_Tablet` AVD's
  network sometimes comes up (or drops) without a `VALIDATED` default — the
  simulated "AndroidWifi" AP fails its captive-portal check — and then the
  app's backend login hangs for the full timeout (`Login precondition failed`).
  `DriverManager._ensure_connectivity()` runs before every class: it checks
  `dumpsys connectivity` and, **only if the default is non-validated**, cycles
  Wi-Fi off/on and waits up to 30s for it to validate. It never blindly
  disables Wi-Fi (on some boots Wi-Fi is the only network). Manual check:
  `adb shell dumpsys connectivity | grep "Active default network"` and look for
  `VALIDATED` in that network's capabilities; `adb shell svc wifi disable; adb
  shell svc wifi enable` usually fixes it.
- **The RN view tree is virtualised.** Fields above/below the viewport are
  absent from `page_source` until scrolled near — use `BasePage.swipe_to(locator)`
  before touching anything off-screen.
- **Most panels/rows are one flattened element.** A Sales History card, a cart
  line, an order-details panel each render as a single `View` whose
  `content-desc` is every field newline-joined. Locate by
  `descriptionContains("<SO-… / SKU / unique text>")` and parse fields out of
  the string (see `SalesHistoryPage._fields_from_desc`, `CreateSaleOrderPage.get_cart_line`).
- **The app renders in a ~1200×1536 window** centred on the 2560×1600 tablet
  (bounds start at x≈680) — this is Android's freeform/windowed mode, not a bug.
- **First cold launch** can show Android's tablet "See and do more / Got it"
  windowing hint (a system overlay, not app UI). Dismiss with
  `UiSelector().text("Got it")` if it blocks interaction.
- `AppiumBy.ID` does not resolve this app's ids — use `UiSelector().resourceId()`
  or `content-desc` (same as khub-pos-tests).

### Sale Order / Fulfillment locator notes (captured live 2026-09-03)
- **Hamburger**: first clickable `android.view.View` in the app (no id/desc).
- **Nav drawer items**: `content-desc` = "Home" / "Fulfillment" / "Sales History" / …
- **Sales History**: `+` FAB is the only `Button` with no `content-desc`. Each
  order card's `content-desc` carries Order Number / Order Type / Invoice Status
  / Status / Sale Total / Business Name; its ••• is `content-desc="Show menu"`.
  The FAB sometimes **expands into a speed-dial** instead of navigating
  straight to Create Sale Order - mini-FABs "Sale Order" / "Sale Return"
  appear and the main `+` morphs into an `X` (close) that then sits where `+`
  was, so a blind second tap on the same locator just closes the dial again.
  `SalesHistoryPage.tap_create_sale_order()` handles both: taps the FAB, then
  either finds itself already on Create Sale Order, taps the "Sale Order"
  option if the dial opened, or retries the FAB if neither happened.
- **Create Sale Order**: customer search + product search are each the 1st
  `EditText`; Order Type value renders as a `Button` (`Offsite`→ tap → pick
  `Online`); notes fields keyed by `hint="Notes (Internal)"` / `"Notes (Print on
  Invoice)"`; `Next` = `content-desc="Next"`.
- **Product step**: search by SKU → tap the result (`descriptionContains(sku)`) →
  set qty (2nd `EditText`) → `Add To Cart`. Cart line desc is
  "<name>\n<cat>\n<sku>/<upc>\nQty: <avail>\nPrice *\nSale Price:$<p>\nOrder Qty
  *\nSub Total\n$<sub>\nUnit *\nTotal: $<sub>".
- **Cart Summary / Payment**: totals are individual `content-desc` label+value
  pairs; success dialog text = "SaleOrder has been saved successfully.".
- **Fulfillment**: tabs are `Pending (n)` / `Picking Paused (n)` / `Picked (n)`
  / `Packing (n)` / `Packed (n)` — match with `descriptionStartsWith`. Each
  order card is one flattened content-desc; once assigned it gains a leading
  `Picker Detail\n<user>`.
- **Assign**: tap the (unassigned) card → bottom sheet "This order not been
  assigned" → button **"Assign to me"** → info dialog "Order has been assigned
  to the user '<user>'." → OK.
- **Pick**: reopen the assigned card → "Start Picking" → status-dialog OK →
  red **"Skip Scan Pick All"** → dialog 1 "…still some products to be picked…"
  → **Yes** → dialog 2 "Do you want to confirm picking your order?" →
  **Pick** (not "Yes"/"Confirm"). Then "Start Packing" appears.
- **Pack**: "Start Packing" → red **"Skip Scan Pack All"** → **Yes** → **Pack**
  → success dialog "**SO-<n> has been successfully packed.**" → OK.
- Other dialog confirm-button labels vary — `BasePage.tap_ok(labels=(...))`
  tries a list rather than hard-coding one.

### UOM tier "Add another unit" flow (captured live 2026-10-29)
- The product-step search/Add-To-Cart flow has **no Unit selector** before a
  product is added — all 4 UOM tiers (Piece/Pack/Case/Pallet) share one SKU
  and one search result, so the item always adds at the base Piece tier
  first.
- A cart line belonging to a UOM product shows an extra
  `content-desc="Add another unit"` button next to it. Tapping it opens a
  menu listing **only the tiers not yet in the cart**, by their configured
  label (e.g. `content-desc="Box"` / `"Carton"` / `"Package"`) —
  `CreateSaleOrderLocators.ADD_ANOTHER_UNIT` / `.unit_option(label)`. Tapping
  a label adds that tier as a brand-new, separate cart line immediately —
  there is no intermediate confirmation step.
- **Order Qty on an already-placed cart line cannot be edited.** The
  "Order Qty *" value renders as a plain `android.view.View` with a `text`
  attribute, not an `EditText` — confirmed live by dumping the node tree and
  by tapping it (nothing opens). Only the **first** tier gets a chosen
  quantity, via the qty stepper shown before "Add To Cart" is tapped
  (`CreateSaleOrderPage.add_product_by_sku`'s `qty` param). Every tier added
  afterward via "Add another unit" is fixed at qty=1 by the app itself —
  `CreateSaleOrderPage.add_product_all_uom_tiers` validates this as the real
  behavior rather than forcing an unreachable quantity. (The cart line *does*
  have one real `EditText` — the Sale Price field, index 1; "Order Qty" is
  not index 2 as the pre-existing but never-exercised `cart_line_qty_field`/
  `set_cart_quantity` assumed — left in place for if the app ever adds an
  editable qty control, but not used by the UOM scenario.)
- Because all 4 tiers share one SKU, a cart line is only unambiguously
  addressable by **SKU + UPC** (`CreateSaleOrderLocators.cart_line(sku,
  upc)`), never SKU alone.
- The cart list auto-scrolls to reveal each newly-added line, so right after
  adding all 4 tiers the viewport sits near the *last* one added (Pallet).
  `BasePage.swipe_to`'s fixed scroll direction reliably reaches whichever end
  was already closer, but not the other — use `BasePage.swipe_to_either`
  (tries up, then down) rather than guessing a direction, whenever the
  current scroll position relative to the target isn't known.

### Finding new locators
```
venv\Scripts\python.exe scripts/inspect_app.py <tag>      # interactive: navigate, press Enter to dump
```
or `driver.page_source` / `adb exec-out uiautomator dump /dev/tty`. Dumps land
in `scripts/_inspect/`.

---

## Developing New Tests

1. Run the flow manually on the emulator; note each screen.
2. `scripts/inspect_app.py` at each screen to grab locators.
3. Add locators → `locators/<screen>_locators.py`.
4. Add page methods → `pages/<screen>_page.py` (inherit `BasePage`).
5. Write `tests/<module>/test_<feature>.py`, inherit `BaseTest`.
6. Multi-step scenarios: one `test_` method per UI step, share state via class
   attributes (conftest skips the rest of a class after any step fails). See
   khub-pos-tests' `test_split_payment.py` for the pattern.

---

## What Is Automated

| Module | Tests |
|--------|-------|
| **Login** | Valid login → Dashboard; empty-credentials validation errors |
| **Sale Order + Fulfillment** | `tests/fulfillment/test_online_sale_fulfillment.py` — API-built customer + products (`online_sale.product_count` in `data/test_data.yaml`, default 2) → create & fully-pay (Cash) an **Online** sale → validate in Sales History + View Details → assign to me → pick all → pack all → confirm the same `SO-…` in the Packed section. One `test_NN_*` per UI step, shared class state, API test-data via `utilities/api_client.py` (`ApiClient`, ported from khub-pos-tests). Generated names come from `utilities/test_data_names.py` — a realistic business/product name + `QA-<YYMMDD>-<HHMMSS>-<rand>` tag (kept byte-identical across khub-pos-tests / khub-Ecom-tests). |
| **UOM (multi-unit) Sale Order + Fulfillment** | `tests/fulfillment/test_uom_multi_unit_sale_fulfillment.py` — mirrors khub-web-tests' UOM multi-unit scenario (`PWkhubTest/UOM/test_uom_multi_unit_sale_fulfilment_validation_runner.py`). One product configured via the backend API with 4 chained packaging tiers (Piece/Pack/Case/Pallet, custom labels on the top 3 — `ApiClient.create_uom_product`, same payload shape as khub-web-tests' `scripts/create_uom_products_api.py`) is added to a single Online sale as 4 **separate** lines, fully paid, validated (per-tier price × qty = subtotal, cart summary totals, Sales History card, View Details line totals), then taken through the same assign → pick → pack → Packed lifecycle. See "UOM tier add-another-unit flow" below for the live app behavior this is built around. |

Everything else (Sales, Customers, Profile, Scan) is future work.
