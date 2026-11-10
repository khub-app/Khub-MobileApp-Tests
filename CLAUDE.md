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
- **Product step**: search by UPC (not SKU - see below) → tap the result →
  set qty (2nd `EditText`) → `Add To Cart`. Cart line desc is
  "<name>\n<cat>\n<sku>/<upc>\nQty: <avail>\nPrice *\nSale Price:$<p>\nOrder Qty
  *\nSub Total\n$<sub>\nUnit *\nTotal: $<sub>".
  - **Search by SKU is unreliable in this shared preprod catalog - search by
    UPC instead.** `CreateSaleOrderPage.add_product_by_sku(..., upc=...)`
    types the UPC when given. Two SKU-specific traps, both confirmed live
    2026-11-03 on a catalog that had grown to ~18,000+ products across all
    3 QA suites:
    1. **Substring collision**: a short, sequential, auto-generated SKU
       (e.g. `2572`) is a literal substring of other real SKUs (`25720`,
       `25754`, ...) or even product names - a bare `descriptionContains(sku)`
       match silently picks the WRONG product. Locators now anchor on the
       newline around the SKU (`CreateSaleOrderLocators.product_result`,
       `.cart_line`) to rule this out - but anchoring only fixes
       *mismatches*, not the next problem:
    2. **Crowded out of the results entirely**: with enough unrelated
       products sharing that digit string somewhere, the exact SKU match can
       fail to appear in search results AT ALL, for many minutes after
       creation - looks identical to backend index lag (empty results,
       `_search_product_result`'s retry loop exhausts the full
       `search_timeout`) but no amount of waiting fixes it. Searching the
       same product's UPC (random 10-digit, no realistic collision) finds it
       immediately. If a `_search_product_result` failure message says
       "crowded out", that's the cause - pass `upc=` at the call site rather
       than retrying.
- **Cart Summary / Payment**: totals are individual `content-desc` label+value
  pairs; success dialog text = "SaleOrder has been saved successfully.".
- **Fulfillment**: tabs are `Pending (n)` / `Picking Paused (n)` / `Picked (n)`
  / `Packing (n)` / `Packed (n)` — match with `descriptionStartsWith`. Each
  order card is one flattened content-desc; once assigned it gains a leading
  `Picker Detail\n<user>`.
- **Assign**: tap the (unassigned) card → bottom sheet "This order not been
  assigned" → button **"Assign to me"** → info dialog "Order has been assigned
  to the user '<user>'." → OK.
  - **`<user>` is the profile's display username, not the login credential**
    - confirmed live 2026-11-03: logging in as `preprod`/`Password@123`
    produced "...assigned to the user 'eaglews'." The authenticate response's
    `entity.user.username` field ("eaglews") is the profile username; the
    login field (`entity.user... login: "preprod"`, only visible by decoding
    the JWT) is a separate thing. `ApiClient._login()` now captures the
    profile username as `self.profile_username`, and both fulfillment tests
    read `logged_in_user` from it at runtime (`test_01`) instead of assuming
    it equals `data/test_data.yaml`'s login username.
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

### Promotions — mobile test data (cross-repo, captured 2026-11-09)

The Admin app has **no Promotions screen** — confirmed live by dumping the
nav drawer (flat items + the collapsible "Inventory" group): Home,
Fulfillment, Sales History, Customers, Profile, Products, Daily Summary
Report, Terms & Conditions, Contact KHUB, Stocks, Stock Locations, Expiring
Soon, Purchase Order, Sales Return. Promotions are created/managed only on
the web portal (`/tenant/api/v1/marketing/promotions`); mobile can only
consume their effect on the Sale Order screen.

Mobile tests therefore **never create a promotion or its product**. A
prerequisite script in the sibling `khub-web-tests` repo does that:
```
python scripts/create_mobile_promotion_scenarios_api.py --env=preprod
```
(run from `khub-web-tests`, its own venv — takes well under a minute, pure
API). It fully overwrites `khub-web-tests/testdata/mobile_promotion_scenarios_<env>.json`
with fresh products/customer/promotion(s) for 7 scenarios
(`multi_tier`, `phase2_boundary`, `repick`, `bxgy`, `buy3_get2_half_off`,
`validity_window`, `customer_targeting` — see
`khub-web-tests/docs/mobile_promotion_api_handoff.md` for the full contract).
`customer_targeting` is the one exception to "fresh every run": its
Customer Group + member/non-member customers are a STABLE, manually-
provisioned fixture (no API for creating a Customer Group was ever found —
see that scenario's own builder docstring in the script for exactly how to
recreate it if it's ever deleted). Its product and promotion are still
fresh every run, same as everything else.
`utilities/promotion_data.py` reads that file by absolute sibling-repo path
(`get_scenario(name, env=...)`) — never hardcode a UPC/promotion name/id
from an example run, they're stale the moment a new one runs. The promo
products are plain UOM products (`create_uom_product` defaults: base_cost
200, pack/case/pallet qty 5/6/30 → Piece $250/Pack $1250/Case $7500/Pallet
$225000), so every existing UOM cart-flow method (`add_product_all_uom_tiers`,
`get_cart_line`, etc.) applies unchanged — the data file just doesn't carry
a SKU (it's created by a different repo/script), so resolve one at runtime
via `ApiClient.get_product_by_upc(upc)`.

### Promotions — live app behavior (captured 2026-11-09)

A promoted cart line's content-desc adds up to 3 pieces of info to the
plain shape (see `cart_line` above) — `CreateSaleOrderPage.get_cart_line`
parses all of it:
- A banner line right after `Qty: <avail>`: `"<promo name> · <percent>% off"`
  on an actively-discounted line, or `"<promo name> · rewards line <n>"` on
  a BXGY **trigger** line (never itself discounted — the promotion payload
  sets `skip_discounted_trigger: true`).
- Two extra bare `"$<amount>"` lines between `Sale Price:$<p>` and
  `Order Qty *` (original price, then discounted price) — **only** when the
  line's current qty is actually inside the promo's qualifying range. Outside
  that range the banner and these two lines are **both** absent entirely,
  even though the line is still promo-eligible (confirmed at qty 1 and qty 6
  against a promo configured for qty 2–5 — no partial/clamped discount,
  just none).
- Under `Order Qty *`: `"Range: <min>–<max>"` for a Basic promo (shown
  regardless of whether the current qty is in range), or `"Min: <trigger_qty>"`
  / `"Max: <max_reward_qty>"` for a BXGY trigger/reward line respectively.
- A line's own `"Sub Total"` is **always** qty × the undiscounted price —
  on a discounted line this is NOT what the line is actually charged.
  `"Total:"` is the real charged amount. Cart Summary's own `"Sub Total"`
  already nets out every line's discount (it equals the sum of `Total:`,
  not `Sub Total`, across lines) and adds a new `"Promo Savings"` field
  (e.g. `"-$100.00"`) for the aggregate discount — `CartSummaryPage.get_promo_savings()`.
  Like `get_tax`, the row is omitted entirely (not `"$0.00"`) when no line
  has an active promotion.
- Two overlapping Basic promotions on the same product auto-apply the
  **higher** discount (confirmed: 15%/25% configured, 25% applied) — no
  manual picker, nothing to switch.
- BXGY: adding the reward product before the trigger qty is met shows a
  plain, undiscounted line; adding the trigger at its qty re-evaluates the
  *already-in-cart* reward line live and it becomes discounted — no need to
  re-add or refresh it.
- **BXGY only works cross-product.** A self-referential BXGY (trigger and
  reward pointing at the SAME product/unit, so there is only ever one cart
  line for it) does NOT render any discount — confirmed live 2026-11-09:
  the single resulting line shows the promotion's name with a bare
  `"trigger"` tag and no discount at all, even once qty meets `trigger_qty`
  (no banner, no discounted-price pair, Sub Total == Total for the full
  undiscounted amount). The reward mechanism needs a structurally separate
  line to attach its discount to.
- **A BXGY reward line's qty vs. `max_reward_qty` is a hard on/off
  boundary, not partial** — confirmed live 2026-11-09 (trigger_qty=3,
  max_reward_qty=2, 50% off): at reward qty <= `max_reward_qty` every unit
  on that line discounts; at reward qty > `max_reward_qty` the line is
  **completely plain** - no banner, no `"Max:"` indicator, nothing. This
  differs from a Basic promo's `"Range:"` line, which stays visible even
  when the current qty is out of range.
- **View Details' own per-line "Extended" field is wrong for a discounted
  line** — confirmed live: a line with Sale Price $250.00 × Order Qty 2 ×
  "Discount 20.00%" showed `Extended $300.00`, not the correct $400.00 that
  every other source of truth agrees on (the cart's own `Total:`, Cart
  Summary's Sub Total/Grand Total, the Sales History card's Sale Total, and
  this same order's own View Details order-level Sub Total, which only
  reconciles against $400 for that line — not $300, which doesn't even sum
  correctly into the order total). `$300.00 == $250 × 1.20` — the field
  applies the discount percent with the wrong sign and ignores Order Qty.
  This is a real app display bug in View Details, not a mobile automation
  issue — `test_promotion_multi_tier.py`'s View Details step therefore only
  checks non-discounted tier lines against it (and logs a warning for the
  discounted one) rather than asserting a value the screen gets wrong.
- **No cart line can be edited or removed once placed** — not just Order
  Qty (already documented for UOM): the cart's "Show menu" button is a
  single **order-level** control (`Search to Add Product` / `Search From
  Cart` / `Dismiss menu`), not a per-line menu, and there is no other
  remove/delete affordance on a line (`clickable="false"` on the whole
  line element). To probe a promotion at several quantities,
  `CreateSaleOrderPage.discard_order()` backs all the way out of the
  in-progress order instead (Android back from step 1 opens a
  "Confirmation" dialog; "Go Back" discards cleanly, confirmed safe across
  several repeated fresh orders in one session) — see
  `test_promotion_phase2_boundary.py`.
- **Adding the same SKU+UPC to the cart a second time merges into the
  existing line** (qty increments) rather than creating a duplicate —
  confirmed live 2026-11-09. This is how `test_promotion_bxgy.py`
  demonstrates a BXGY trigger crossing its qty threshold live (no qty-edit
  or remove feature needed): add the trigger once below `trigger_qty`,
  confirm the reward is still plain, add it again to push the same line's
  qty up to `trigger_qty`, confirm the reward discounts live.
- **Self-referential BXGY does not work at all** — a promotion whose
  trigger AND reward point at the same product/unit (so there is only ever
  one cart line for it) shows that line with a bare `"<promo name> ·
  trigger"` tag and **zero** discount, even once qty meets `trigger_qty` —
  confirmed live 2026-11-09. The reward mechanism needs a structurally
  separate line to attach its discount to; `buy3_get2_half_off` is built
  cross-product (two different products) specifically because of this.
- **Cart Summary's Promo Savings correctly sums MULTIPLE independent,
  simultaneously-active promotions** across different lines in one order —
  confirmed live 2026-11-10 with 3 different promotions (two Basic, one
  BXGY reward) in a single cart: the aggregate figure is the exact sum of
  each line's own discount, not just whichever applied last.
- **A manual "Additional Discount" (Cart Summary's own editable
  `ADDITIONAL_DISCOUNT_FIELD`) stacks cleanly on top of an active
  promotion** — confirmed live 2026-11-10: entering it leaves the
  promo-discounted Sub Total AND Promo Savings completely unchanged: it
  only reduces Grand Total by exactly the entered amount. No double-
  discount, no clobbering of the promo - the two mechanisms are fully
  independent. `CartSummaryPage.set_additional_discount(amount)`.
- **A promotion outside its time window (not yet started, or already
  ended) shows nothing at all** — confirmed live 2026-11-10: no banner, no
  discounted-price pair, and (unlike a qty-range-ineligible Basic promo,
  which still shows its `"Range:"` indicator) not even that. Same as a
  customer-ineligible promotion (see Customer Group targeting below) - a
  temporally- or customer-ineligible promotion leaves no trace on the line
  at all, while a qty-ineligible one still shows its range.
- **A promotion scoped to a Customer Group (`applicable_to: 3`,
  `customer_group_ids: [<id>]` in the `POST .../marketing/promotions`
  payload - confirmed live 2026-11-10 by creating one through the real
  portal UI, Marketing > Promotions > Create Promotion > "Apply To" >
  "Only customers within the following Customer Groups", and reading it
  back via `GET .../marketing/promotions/list`) only discounts for
  customers in that group** — a customer outside it sees a completely
  plain line, same "no trace at all" behavior as the time-window case
  above. No API endpoint for *creating* a Customer Group was found (the
  portal's own create-group flow never surfaced a capturable request), so
  that part of the fixture is manually provisioned once rather than
  recreated per run — see `create_mobile_promotion_scenarios_api.py`'s
  `_scenario_customer_targeting` docstring for the exact recreation steps.

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
| **Promotions** | `tests/promotions/` — 9 promotion-engine scenarios from the cross-repo data contract (see "Promotions — mobile test data" below), each a full Online sale, fully paid, validated end-to-end against the live cart/Cart Summary/Sales History/View Details: `test_promotion_multi_tier.py` (one Basic promotion across all 4 UOM tiers of one product), `test_promotion_phase2_boundary.py` (qty-range boundary — discount on at qty 2/3/5, off at 1/6, each a fresh discarded order except the one carried to checkout), `test_promotion_repick.py` (two overlapping promotions, the higher auto-applies — no switch/picker UI exists on this app, confirmed live, so none is exercised), `test_promotion_bxgy.py` (trigger product reaching its qty live-discounts a different reward product already in the cart), `test_promotion_buy3_get2.py` (same BXGY mechanism, trigger_qty=3/max_reward_qty=2/50% — additionally proves the reward-qty upper boundary is a hard on/off, not partial), `test_promotion_multi_promo_cart.py` (3 independent promotions in one cart — Cart Summary's Promo Savings correctly sums all 3, reusing existing scenario products rather than new data), `test_promotion_additional_discount_stacking.py` (a manual Additional Discount stacks cleanly on top of an active promo — independent fields, no double-counting), `test_promotion_validity_window.py` (a not-yet-started or already-expired promotion applies no discount at all), `test_promotion_customer_targeting.py` (a promotion scoped to one Customer Group discounts only its members, confirmed negative for a non-member customer). Mobile never creates any promotion or product itself — see "Promotions — mobile test data (cross-repo)" below for the full data contract and "Promotions — live app behavior" for what the cart/invoice actually show, including a confirmed View Details display bug on discounted lines, a confirmed non-working self-referential-BXGY configuration, and the Customer Group targeting fixture. |

Everything else (Sales, Customers, Profile, Scan) is future work.

### Sales Return — investigated 2026-11-10, NOT YET automatable

A 5th promotion scenario ("return a promoted order and confirm the refund
reflects the discounted amount actually paid") was attempted and could not
be completed - not a quality gap, a genuine missing prerequisite. Full
findings, so this isn't re-investigated from scratch later:

- `DashboardPage.go_to_sales_return()` / `NavDrawerPage.go_to_sales_return()`
  exist, are tested, and work (Sales Return sits inside the collapsible
  "Inventory" drawer group, same as Stock Locations etc. - see
  `NavDrawerLocators.INVENTORY_EXPANDER_COLLAPSED`).
- That screen is a **read-only log of already-completed returns** - cards
  show `Return Number RE-...` / `Invoice Total` / `Business Name` etc. in
  the usual flattened content-desc shape, but there is no FAB or any other
  control to start a new one. `pages/sales_return_page.py` reflects this
  (read-only for now).
- Exhaustively checked every other plausible entry point, live, on both the
  mobile app and the web portal (Chrome automation, logged in as the same
  preprod tenant): a Sales History order card's "Show menu" (checked on
  both a Pending and a fully-Packed order) only offers View Details/Print
  Invoice/Send Email; Order Details' own tabs (Order Detail/Payment
  History) have nothing either.
- On the **web portal**, the equivalent action (Sales History row's "..."
  menu → "Return") exists, but **only appears once an order's Order Status
  reaches "Completed"** - confirmed by comparing a `Packed`/`Ready For
  Delivery` order (no Return option) against an unrelated, pre-existing
  `Completed` order (Return option present). This project's own Fulfillment
  automation only ever drives an order to **Packed** - reaching Completed
  needs the separate Delivery & Shipping execute/deliver flow, which has
  never been explored or automated here. That's the real prerequisite
  blocking this scenario, on mobile or web.
- No API shortcut was found either (checked both sibling repos for an
  "execute"/"deliver"/"complete order" script, the way Promotions has
  `create_mobile_promotion_scenarios_api.py` - nothing exists).
- Actually clicking the web portal's own "Complete Return" button (to learn
  the finalize payload, the same way the Promotions API was reverse-
  engineered) was correctly blocked by the permission system: that is a
  real, irreversible refund transaction against a real order, executed by
  direct browser action outside this project's own sandboxed Appium test
  framework - not something to click through directly, unlike the safe,
  isolated QA-tagged data this project creates everywhere else. That
  confirmation request was not completed; the draft return it started was
  abandoned, not finished.

**To unblock this in the future**: either (a) automate the Delivery &
Shipping execute/deliver flow first (a prerequisite module in its own
right, comparable in scope to Fulfillment's own pick/pack), or (b) find/
build a backend API that marks an order Completed without the UI flow
(mirroring how Promotions bypasses its own UI) - worth asking the web/QA
side about directly, the way the promotion payloads were handed off.
