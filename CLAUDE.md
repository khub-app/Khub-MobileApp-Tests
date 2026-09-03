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

```
venv\Scripts\python.exe -m pytest tests/ -v
venv\Scripts\python.exe -m pytest tests/login/ -v
venv\Scripts\python.exe -m pytest tests/ -v -m smoke
venv\Scripts\python.exe -m pytest tests/ -v --env=real_device
```

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
│   └── inspect_app.py       # launch the app + dump page_source/screenshot for locator work
├── conftest.py              # driver fixture, per-step screenshots, fail-fast within a class, Allure gen
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
  `is_login_successful()` waits up to 60s for the Dashboard.
- **First cold launch** can show Android's tablet "See and do more / Got it"
  windowing hint (a system overlay, not app UI). Dismiss with
  `UiSelector().text("Got it")` if it blocks interaction.
- `AppiumBy.ID` does not resolve this app's ids — use `UiSelector().resourceId()`
  or `content-desc` (same as khub-pos-tests).

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

Everything else (Fulfillment, Sales, Customers, Profile, Scan) is future work.
