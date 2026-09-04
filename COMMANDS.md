# Khub Admin App Automation — Command Reference

Project: `C:\Users\mzees\KhubAutomation\khub-mobileApp-tests`
App: **Khub PreProd Admin** (`com.esolutions.demotaxadmin`) — Appium + pytest.

Mirrors `khub-pos-tests`' command flow (RunConfig/Tags sheets → `run_mobile_tests.ps1`).

---

## One-time setup

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

**The APK is gitignored.** Get `preprod-admin.apk` from the dev team and place it
at `data\apk\preprod-admin.apk`.

---

## Running the suite (3 commands, 2 windows)

**Window 1 — Appium (leave running):**

```powershell
appium --allow-insecure uiautomator2:chromedriver_autodownload
```

**Window 2 — emulator, then tests:**

```powershell
& "$env:ANDROID_HOME\emulator\emulator.exe" -avd Pixel_Tablet -gpu off
```

Wait for the home screen to fully load, then:

```powershell
.\run_mobile_tests.ps1
```

`run_mobile_tests.ps1` reads `data\test_data.xlsx` → **RunConfig** sheet (which
environment + Smoke/Regression toggle) and runs the matching tests. Which test
carries which marker comes from the **Tags** sheet (`FilePath | smoke |
regression`) — `conftest.py` applies those markers automatically at collection
time. The Allure HTML report (`reports\allure-report\index.html`) regenerates
automatically when the run finishes.

### One-off overrides

```powershell
.\run_mobile_tests.ps1 -Path tests/login -Suite ""      # run a folder, ignore markers
.\run_mobile_tests.ps1 -Env real_device                 # target a physical device
```

### Direct pytest (bypass the sheet)

```powershell
venv\Scripts\python.exe -m pytest tests/ -v
venv\Scripts\python.exe -m pytest tests/login/ -v
venv\Scripts\python.exe -m pytest tests/ -v -m smoke
venv\Scripts\python.exe -m pytest tests/ -v --env=real_device
```

---

## Editing the run config / tags

`data\test_data.xlsx` is regenerated from `scripts\gen_test_data_xlsx.py` — edit
that script (the reviewable source of truth) and rebuild:

```powershell
venv\Scripts\python.exe scripts\gen_test_data_xlsx.py
```

Sheets:

| Sheet | Purpose |
|-------|---------|
| `RunConfig` | `Environment` (emulator / real_device) + `Smoke` / `Regression` = Yes/No |
| `Tags` | one row per test file; `Yes` in `smoke` / `regression` auto-applies that marker |
| `TestConfigs` | named test inputs the app UI never surfaces |

### After adding / changing a tag

1. Add the row in `scripts\gen_test_data_xlsx.py` (`TAGS = [...]`) and rebuild:
   ```powershell
   venv\Scripts\python.exe scripts\gen_test_data_xlsx.py
   ```
2. Set the matching suite to `Yes` in the `RunConfig` sheet block of that same
   script if it isn't already, and rebuild again.
3. Run the tagged tests — `conftest.py` reads the `Tags` sheet at collection
   time and applies the markers, so this is all it takes:
   ```powershell
   .\run_mobile_tests.ps1
   ```
   Verify the run header prints the expected `Marker(s)` and that collection
   logs `[INFO] Applied Excel tags to N test items`.

   To run just the newly tagged file/marker without touching the sheet:
   ```powershell
   venv\Scripts\python.exe -m pytest tests/ -v -m regression --env=emulator
   venv\Scripts\python.exe -m pytest tests/fulfillment/test_online_sale_fulfillment.py -v --env=emulator
   ```

---

## Adding / updating the APK build

With the emulator running:

```powershell
& "$env:ANDROID_HOME\platform-tools\adb.exe" install -r -g data\apk\preprod-admin.apk
```

`-r` reinstalls in place (keeps app data), `-g` grants runtime permissions.
`INSTALL_FAILED_UPDATE_INCOMPATIBLE` means a different signing key — uninstall
first, then reinstall:

```powershell
& "$env:ANDROID_HOME\platform-tools\adb.exe" uninstall com.esolutions.demotaxadmin
```

Verify:

```powershell
& "$env:ANDROID_HOME\platform-tools\adb.exe" shell dumpsys package com.esolutions.demotaxadmin | Select-String "versionCode|versionName|lastUpdateTime"
```

---

## Locator work

```powershell
venv\Scripts\python.exe scripts\inspect_app.py <tag>      # navigate, press Enter to dump page_source + screenshot
```

Dumps land in `scripts\_inspect\` (gitignored).

---

## ⚠️ Only run ONE emulator instance at a time

Two sessions driving the same AVD causes device contention that looks like
broken locators but isn't.
