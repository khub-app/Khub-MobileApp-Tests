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
| **Promotions** | `tests/promotions/` — 9 promotion-engine scenarios from the cross-repo data contract (see "Promotions — mobile test data" below), each a full Online sale, fully paid, validated end-to-end against the live cart/Cart Summary/Sales History/View Details: `test_promotion_multi_tier.py` (one Basic promotion across all 4 UOM tiers of one product), `test_promotion_phase2_boundary.py` (qty-range boundary — discount on at qty 2/3/5, off at 1/6, each a fresh discarded order except the one carried to checkout), `test_promotion_repick.py` (two overlapping promotions, the higher auto-applies — no switch/picker UI exists on this app, confirmed live, so none is exercised), `test_promotion_bxgy.py` (trigger product reaching its qty live-discounts a different reward product already in the cart), `test_promotion_buy3_get2.py` (same BXGY mechanism, trigger_qty=3/max_reward_qty=2/50% — additionally proves the reward-qty upper boundary is a hard on/off, not partial), `test_promotion_multi_promo_cart.py` (3 independent promotions in one cart — Cart Summary's Promo Savings correctly sums all 3, reusing existing scenario products rather than new data), `test_promotion_additional_discount_stacking.py` (a manual Additional Discount stacks cleanly on top of an active promo — independent fields, no double-counting), `test_promotion_validity_window.py` (a not-yet-started or already-expired promotion applies no discount at all), `test_promotion_customer_targeting.py` (a promotion scoped to one Customer Group discounts only its members, confirmed negative for a non-member customer). Mobile never creates any promotion or product itself for these 9 — see "Promotions — mobile test data (cross-repo)" below for the full data contract and "Promotions — live app behavior" for what the cart/invoice actually show, including a confirmed View Details display bug on discounted lines, a confirmed non-working self-referential-BXGY configuration, and the Customer Group targeting fixture. A `utilities/promotion_asserts.py` helper (`assert_promo_state`) wraps every `is_promo_active` assertion across these files — on an unexpected discount it checks whether the live promo's name starts with `Mobile_` (this suite's own naming convention) and, if not, flags it as likely shared-tenant promotion contamination (see "Shared-tenant promotion contamination" below) rather than a test/app bug. A 10th scenario, `test_promotion_tier_pricing.py`, is NOT part of that cross-repo contract (it needs a product with Customer Tier prices, a field only this project's own `ApiClient` creates) — see "Customer Tier pricing vs. Promotions" below. |
| **Label Management** | `tests/labels/test_label_management_create_label.py` — Phase 1 (see "Label Management" below): creates a Product label with a unique name, both Fulfillment and Invoice display destinations enabled, background `#817CDB` / text `#FFFFFF` via the color picker's Hex input, confirms the "Tag has been saved successfully." message, and confirms the new card appears in the list. `tests/labels/test_label_management_product_fulfillment.py` — Phases 2-5: a label + product created via API (`ApiClient.create_product_with_new_label` — sidesteps the mobile UI's own broken Category picker, see below) goes through a full paid Online Sale Order and Fulfillment (assign → pick → pack); confirms the label is visible on the active Picking list's per-product chip (where `show_on_fulfillment` actually renders — not the Fulfillment order card, whose own "Tags" field is an unrelated order-level feature) and on the Print Invoice page opened from Sales History (where `show_on_invoice` actually renders — a real web page in the device's own Chrome browser, not a screen in this app, see `pages/print_invoice_page.py`), and logs (without asserting, since this specific screen never shows it) that the label does not appear on View Details. Native in-app product creation (assigning a label to a product *through the UI*) remains blocked by the Category picker — see below. |

Everything else (Sales, Customers, Scan) is future work.

### Customer Tier pricing vs. Promotions — confirmed live 2026-11-13

Two fields existed on the live portal, unused by this project, even though
their payload plumbing already existed (unused) in `create_customer` and
`create_product`:
- **Add Customer form, Basic Details**: a **Tier** dropdown (`None` / Tier
  1-5) — reverse-engineered live: it's a fixed client-side enum, no network
  call fetches it, and the backend field is plain `tier_id` (int 1-5 or
  `null`), confirmed round-tripping correctly on `GET
  /tenant/api/v1/sale/customers/{id}`.
- **A product's Define Pricing grid**: `Tier 1 SP ($)` … `Tier 5 SP ($)`
  columns per unit — backend field `unit_price.unit_price_tiers`, a list of
  `{"tier_id": 1..5, "price": ...}` (already being sent as all-zero
  placeholders by the existing `create_product`/`create_uom_product`
  payloads — `price: 0` means "no override for that tier").

New, separate `ApiClient` methods (existing `create_customer`/
`create_product`/`create_uom_product` untouched, same convention as Label
Management's own API methods): `create_customer_with_tier(tier_id)`,
`create_product_with_tier_prices(category_id, channels, tier_prices:
{tier_id: price, ...}, price=...)`, and `create_promotion(product_id,
channel_id, reward_percent, trigger_qty=1, max_reward_qty=100, ...)` (a
Basic/percent-off promotion, same payload shape as khub-web-tests'
`create_mobile_promotion_scenarios_api.py` but kept local to this project
since it targets a product only this project creates — one with tier
prices, outside that script's fixed 7-scenario contract).

**Live app behavior, confirmed via a throwaway Appium probe before writing
`tests/promotions/test_promotion_tier_pricing.py`** — NOT a simple "pick
whichever of (tier price, promo-discount-of-the-original-price) is lower"
comparison:
1. A non-zero `Tier <n> SP` for the customer's own tier **unconditionally
   replaces** the product's regular Sale Price as the cart line's base
   price — confirmed in **both directions**: tier price $100 vs. regular
   $250 shows $100 in the cart; tier price $300 vs. regular $250 shows
   $300. The tier price is simply authoritative once non-zero — there is
   no "use whichever is lower" check at this step, even when the tier
   price is the *higher* number.
2. Any active promotion on the product still applies its percent-off
   **on top of** whichever base step 1 produced (it **stacks** — the
   engine does not compare "tier price" against "promo off the regular
   price" and pick one). Confirmed with tier=$100, regular=$250, promo=20%:
   the cart line's own "Sale Price" is $100 (not $250), the promo banner's
   "original" price is $100 (not $250), and the discounted price is $80
   (not $100, not $200 = 250×0.8).
3. Cart Summary's own "Sub Total" already nets out this line's discount
   (same documented behavior as every other promotion scenario here) — it
   equals $80 here, not the plain tier price $100.

The net effect is still exactly "lowest price always wins" as an
end-to-end *outcome* ($80 < plain tier $100 < promo-off-regular $200 <
full $250), even though the underlying *mechanism* is "tier overrides
base unconditionally, promotion still stacks on top" rather than a single
`min()` over two candidates. `test_promotion_tier_pricing.py` asserts both
the mechanism (cart line's `sale_price`/`promo_original_price`/
`promo_discounted_price` fields) and that outcome ordering, then carries
the sale through Cart Summary, Cash payment, Sales History and View
Details to confirm the paid invoice reflects the tier-then-promo amount
throughout.

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

### Shared-tenant promotion contamination — confirmed live 2026-11-11/12

The preprod tenant is shared across all 3 QA suites AND real manual testers
(Marketing > Promotions lists ~95+ promotions going back months, many
named after people - "Nihal sale", "Danish Javed test permotions", etc.).
Twice in one night, a promotion **not created by this suite** silently
discounted this suite's own freshly-created scenario products and broke
otherwise-passing promotion tests (`test_promotion_buy3_get2.py`,
`test_promotion_validity_window.py`, and - less obviously - caused
`test_promotion_multi_tier.py`'s tier-add step to fail by inflating a
cart line's rendered height): "Aaquil123" (deleted) and "new years"
(deleted, id=95).

**How this actually happens** - reverse-engineered live via the portal's
own promotion edit screen, NOT a toggle: a promotion's product scope is
set via its own "Add Sources" picker (Marketing > Promotions > edit >
"Add Sources"). Leaving that picker's Search/Category/Brand filters blank
shows the ENTIRE catalog as candidates; someone then selected a large
batch of rows from that unfiltered list (confirmed - "new years" had ~100
individual products explicitly listed in its `promotion_details`,
including several of this suite's own scenario products that merely
*happened to already exist* when that selection was made). A product
created *after* such a promotion's sources were picked is NOT swept in -
this is a frozen snapshot, not a live "all products" rule. So the risk is
real but bounded: only to promotions assembled broadly (or edited to add
new sources later) against products that already existed at that moment.

**Diagnosis going forward**: `utilities/promotion_asserts.py`'s
`assert_promo_state` flags this automatically - any promotion test
failure where the unexpectedly-active promo's name does NOT start with
`Mobile_` almost certainly means another stray promotion is live again.
Check Marketing > Promotions on the web portal (preprod.ikhub.biz) for one
covering the SKU named in the failure message, confirm with a teammate
whether it's still needed, and delete it if not (`DELETE
/tenant/api/v1/marketing/promotions/{id}` via `ApiClient`, or the
portal's row-menu "Delete" - both confirmed working live).

### `validity_window` test data ages out in real time — confirmed 2026-11-12

`mobile_promotion_scenarios_<env>.json`'s `not_started` promo is built with
`start_datetime = generation_time + 2 days` (see
`create_mobile_promotion_scenarios_api.py`'s `_scenario_validity_window()`).
That's relative to *generation* time, not run time - if the data file isn't
regenerated and more than ~2 days pass (e.g. this repo's own session
spanning past midnight into the next calendar day), the "not started"
promotion's start time slides into the past and the promo goes live for
real, exactly like any other active promotion would. Confirmed live
2026-11-12: `test_promotion_validity_window.py::test_04` failed because
`Mobile_NotStarted_9571532422` (generated 2026-11-10, start time
2026-11-12 ~01:23) was by then genuinely active - correctly flagged by
`assert_promo_state` as "one of our own Mobile_ promotions" (a real
data-state issue, not shared-tenant contamination) rather than a code bug.
**Fix**: regenerate the scenario data
(`python scripts/create_mobile_promotion_scenarios_api.py --env=preprod`
in `khub-web-tests`) before relying on `validity_window` again if its
JSON file is more than a day or two old.

## Label Management

### Phase 1: Create a Product Label — confirmed live 2026-11-12, automated

`tests/labels/test_label_management_create_label.py` / `pages/profile_page.py`
/ `pages/label_management_page.py` / `locators/label_management_locators.py`.

- Reached via the bottom tab bar's **Profile** tab (not the hamburger nav
  drawer) → **Label Management** menu item. This is a plain list of label
  cards (`"<name>\nProduct Label\nStatus\nActive\nLabel Preview\n<name>\n
  Fulfillment\nInvoice[\nDescription\n<desc>]"`, same flattened-View shape
  as everywhere else) plus a single unlabeled `+` `Button` FAB (same
  pattern as Sales History's FAB).
- **Create Label modal fields** (all confirmed by actually creating one
  end-to-end): Label Name (1st EditText) → Label Type dropdown (shows
  `"Select"` until chosen; options `"Product"` / `"Order"` only appear
  once tapped) → once Label Type = Product, a **"Display product labels
  on"** row appears with two real `CheckBox`-backed options, `Fulfillment`
  and `Invoice` (tap the wrapping View, not just the CheckBox - both work,
  confirmed) → an Active toggle (defaults to Active, not exercised) →
  Background Color / Text Color fields, each showing their current value
  as a literal hex string (`"#FFFFFF"` / `"#000000"` by factory default)
  → Description (last EditText) → red **"Create tag"** button.
- **Color picker has no accessible "pick purple" swatch.** Tapping a color
  field opens a dialog with a "Hex" input (a plain EditText, e.g. holding
  `"#FFFFFF"`) and a "Presets" swatch grid below it - but the preset
  swatches carry no color value in any accessibility attribute (plain
  `View`s, no content-desc), so there is no reliable way to pick "purple"
  from the grid itself. **Typing the exact hex into the Hex field and
  tapping "Apply" is the correct, robust approach** - it's also literally
  what the scenario spec's hex codes (`#817CDB` / `#FFFFFF`) are for,
  rather than eyeballing a swatch.
- **`driver.hide_keyboard()` closes this entire modal, not just the
  keyboard** - confirmed live: it falls back to an Android BACK press on
  this screen (a dismissable dialog, confirmed via its `Scrim` element),
  which dismisses the whole Create Label form and silently discards
  everything typed. `CreateLabelPage` never calls it; tapping the next
  field directly is suffient, no explicit hide-keyboard needed between
  fields on this modal.
- Success: an info banner `"Info\nTag has been saved successfully."`
  appears, and the new card is immediately visible at the top of the
  Label Management list.
- Selecting a label for a product (Phase 2) uses a **different**,
  multi-select picker (opened from the Basic Info page's Labels field) -
  a plain list of label names with NO checkboxes, each tap adding a chip
  to a "Selected" preview, committed via a separate **Apply** button
  (confirmed live: this one DOES respond to a plain `.click()` by
  accessibility id, unlike the Category picker below). A selected label
  renders in the product form as a chip with a **Delete** (×) button next
  to it - `BasePage.get_element_color()` (added for this purpose) can
  sample that chip's rendered background/text color via a screenshot
  pixel read, since content-desc carries no color information.

### Phases 2-5: automated via an API-created labeled product — confirmed live 2026-11-12

The Category-picker blocker below (product creation via the mobile UI)
still stands, but Phases 2-5 don't need the UI product-creation flow at
all: `utilities/api_client.py` gained standalone methods (separate from
`create_product`/`create_uom_product`, which are untouched) that create a
Label Management label and a product carrying it entirely via the
backend API:
- `ApiClient.create_product_label(label_name, bg_color, text_color, ...)`
  → `POST /tenant/api/v1/catalog/tags/v2`.
- `ApiClient.get_product_label_id(label_name)` /
  `ApiClient.set_product_labels(product_id, tag_ids)` → `GET
  /tenant/api/v1/catalog/tags/list?tag_type=1&status=1&page_size=-1` and
  `PUT /tenant/api/v1/catalog/products/{id}/labels` with `{"tag_ids":
  [...]}` (a full replace of the product's label set, not a toggle/add -
  resend every id it should end up with). All reverse-engineered live from
  the portal's own "Add Label" / "Create New Label" pickers (Product
  Catalog > Products list), the same way the Promotions API was handed off
  earlier in this project.
- `ApiClient.create_product_with_label(category_id, channels, label_name,
  ...)` and the one-call `ApiClient.create_product_with_new_label(
  category_id, channels, ...)` (generates its own uniquely-tagged label
  and product together) compose these on top of the existing, unmodified
  `create_product`.

`tests/labels/test_label_management_product_fulfillment.py` uses this to
drive a full Phases 2-5 scenario (13 steps, all passing): API-created
labeled product + customer → Create Sale Order (Online) → add the
labeled product → Cart Summary → Cash payment → Sales History → View
Details → assign to me → pick → pack → Packed → Print Invoice. Confirmed
findings from building it:

- **The label does NOT render on the View Details ("Order Detail") screen**,
  even though the product's label has `show_on_invoice=True` - its text
  blob (confirmed via a full read) carries the usual Order Info/Payment
  History fields and nothing label-related. `test_08` logs this as a
  warning rather than asserting it, since this specific screen genuinely
  never shows it - `show_on_invoice` targets a different output entirely
  (below).
- **The label DOES render on "Print Invoice"** - confirmed live
  2026-11-13. A Sales History card's "Show menu" → **"Print Invoice"**
  does not open a screen inside this app at all: it opens the invoice as a
  real web page in the device's own **Chrome browser** (`driver.
  current_package` becomes `com.android.chrome`, a separate task with its
  own full browser UI - not a WebView/Custom Tab embedded in the app's own
  task). Each product line there shows its label as a colored chip
  directly under the product name, exact-text match against the label
  name - this is what `show_on_invoice=True` actually controls.
  Automating this needed two things no native screen in this app needs,
  both handled by the new `pages/print_invoice_page.py`:
  - **Chrome's own one-time first-run screen** ("Welcome to Chrome...")
    can appear first - `pm clear` between test classes only clears the
    *admin app's* data, never Chrome's, so this is a function of whatever
    state Chrome itself is in on that device/emulator, not of this test.
    `PrintInvoicePage` dismisses it (`"Use without an account"` etc.) if
    present.
  - **The product table only becomes readable after scrolling once** -
    confirmed live: at 0 scrolls the label/SKU text is absent from
    `driver.page_source` entirely; after 1 scroll it's present. Chrome's
    accessibility bridge only exposes a web page's content once it has
    actually been rendered/scrolled into view, unlike a native screen.
  - Getting back to the app afterward needs `driver.activate_app(
    "com.esolutions.demotaxadmin")`, not a plain Android back press -
    confirmed live that a back press would stay inside Chrome's own
    history (it's a separate task), while `activate_app` correctly resumes
    the admin app exactly where it was (e.g. still on Sales History, same
    order still in the list) rather than restarting it.
  `test_13` asserts the label (and the SKU, to rule out a false-positive
  match against the wrong order) are both present after scrolling.
- **The label does NOT render on the Fulfillment order-summary card either**
  (Pending/Packed tabs) - that card has its own `"Tags"` field with a
  `"+ Add Tag"` button, but confirmed live via a crop screenshot that this
  is a **separate, unrelated, manual order-level tagging feature** (add an
  arbitrary tag to the whole order), not a Label Management product label
  display - it's always present and always empty regardless of any
  product's label.
- **The label DOES render on the active Picking list** (`"Start Picking"` →
  the per-product "To Pick" card), as its own `"Labels:"` row holding an
  exact-text content-desc chip (e.g. `"Halvik QA-..."`), confirmed live via
  `driver.page_source` containing the label name as its own element,
  separate from the product's own `"<sku>/<upc>"` line -
  `FulfillmentLocators.product_label_chip(label_name)` /
  `PickingPage.is_product_label_present(label_name)`. This is what
  `show_on_fulfillment=True` actually controls. `test_10` asserts this.
- **Pixel-color verification of that chip was attempted and deliberately
  left unasserted** - a real, reproducible finding, not a timing bug:
  `driver.page_source`'s reported `bounds` for that exact content-desc node
  is **stable but wrong** across repeated dumps (confirmed by diffing two
  consecutive `page_source` calls with no action between them - identical,
  incorrect bounds both times), a 3s settle wait (no change), and a
  scroll-nudge (shifted the bounds to a *different* still-wrong value, not
  the correct one). Cropping a screenshot at those bounds, or using the
  element's own `screenshot_as_png`, lands on an unrelated sibling row
  (`"Notes:"` or the `"Labels:"` header text) instead of the chip itself -
  seen identically with both techniques, ruling out a race between reading
  location and taking the screenshot. This is a genuine Appium/UiAutomator2
  + RN accessibility bounds-reporting limitation on this one element, not
  an app defect - `PickingPage.get_product_label_bg_color()` still exists
  for future use if a reliable anchor/approach is found (e.g. computing an
  offset from a nearby element with correct bounds), but is not called by
  the test. Separately, `BasePage.get_element_color()` was changed this
  session to sample via the element's own `screenshot_as_png` rather than a
  full-screen screenshot plus manually-read location/size, which fixes a
  real (if narrower) race on non-virtualized screens - e.g. Phase 1's
  Create Label dialog - and remains correct there.

Creating a product (Phase 2, via the mobile app's own UI) requires a Category (marked `*`, required)
before the form can proceed. Live investigation, in order of what was
tried:

1. `Profile` tab → `Products` (nav drawer item, not the Profile menu) →
   tapping its `+` FAB first opens an unexpected **channel picker** popup
   (`"Primary 1"` / `"Secondory"` [sic] / `"Primary"`) - picking a channel
   there does NOT open product creation; it just re-filters the Products
   *list* to that channel. The `+` FAB must be tapped **again**, now that
   a channel is selected, to actually reach "Basic Info" (confirmed live -
   this is the real product-creation entry point, `pane-title: "Basic
   Info"`).
2. Basic Info has, in order: Category\* (tap-to-pick, no EditText) →
   Product Name\* (EditText) → SKU + "Auto generated SKU" toggle → Primary
   UPC / Alternative UPC1 / Alternative UPC2 (EditTexts) → Bin Code / Zone
   / Aisle (EditTexts) → Brand (picker) → Supplier (picker) → **Labels**
   (the multi-select chip picker described above - confirmed working) →
   BO/Online/Featured switches → Status (Active/Discontinue/Inactive) →
   Description (rich-text editor with its own Bold/Italic/etc. toolbar) →
   Media/Upload Images → `Next` button (bottom, confirmed reachable).
3. **The Category picker does not respond to any tap, by any method
   tried.** Confirmed exhaustively live, not a guess from the
   accessibility dump alone (checked an actual screenshot, not just
   `page_source`, to rule out a hidden overlay):
   - `driver.find_element(ACCESSIBILITY_ID, "ACCESSORIES").click()` - no
     change.
   - A raw coordinate tap at the row's own reported bounds' center,
     via Appium's `mobile: clickGesture` - no change.
   - A raw `adb shell input tap <x> <y>` at the same coordinates,
     bypassing Appium's gesture layer entirely - no change.
   - Typing into the picker's own "Search Category" field to filter the
     list down to a single row, then tapping that - no change.
   - None of these closed the dialog, changed the `"Tap to select the
     category"` placeholder text, or advanced `window-id` - the dialog
     state is provably unchanged after every attempt (same list, same
     window, every time).
   - A screenshot taken immediately after one of these taps showed a
     completely ordinary, unobstructed list (no keyboard, no overlay) -
     `adb shell dumpsys input_method` separately showed `mInputShown=true`,
     but the "keyboard" turned out to be the emulator's own floating
     Gboard side-toolbar sitting at the screen's left edge, x<100 in a
     window whose content starts at x=680 - nowhere near the category
     rows, ruled out as the cause.
   - This is a genuine, reproducible blocker, not a shortcut: every tap
     technique this project uses elsewhere was tried, and all of them
     produced zero observable effect on this one specific picker.

Since no product can be saved without a Category, assigning a label
during product creation **through the mobile app's own UI** specifically
remains blocked by this picker. This no longer blocks the Phases 2-5
*scenario* as a whole, though - see the section above: creating the
labeled product via the backend API sidesteps the picker entirely, and
`test_label_management_product_fulfillment.py` carries that product
through the real Sales Order + Fulfillment UI flow end-to-end.

**To unblock the native in-app product-creation flow itself in the
future** (still worth doing - it's the only way to test the picker /
Basic Info form as real users actually experience it): investigate the
Category picker with
fresh eyes on the live emulator (not blind dump-driven guessing) - try a
long-press, a drag/swipe-release instead of a tap, inspecting whether the
row elements sit under an invisible full-screen sibling that intercepts
touches (`a11y-important` siblings at identical bounds were present
throughout the dump but not individually tested), or whether this specific
RN list requires `mobile: clickGesture`'s "duration" to be longer than a
default quick tap. `pages/label_management_page.py` and the Phase 1 test
are solid groundwork to build on once this is cracked - `ProductCreatePage`
itself was never started.
