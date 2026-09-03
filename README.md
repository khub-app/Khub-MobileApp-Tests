# khub-mobileApp-tests

Appium + pytest automation for the **Khub PreProd Admin** Android app
(`com.esolutions.demotaxadmin`). Sibling of `khub-pos-tests` — same framework
patterns, different app.

## Quick start

```powershell
# 1. deps (one time)
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. boot the emulator
& "$env:ANDROID_HOME\emulator\emulator.exe" -avd Pixel_Tablet

# 3. start Appium (separate terminal)
appium

# 4. install the app (one time / on new build)
adb install -r -g data\apk\preprod-admin.apk

# 5. run
venv\Scripts\python.exe -m pytest tests/ -v
```

Report: `reports/allure-report/index.html` (auto-generated after each run).

## Docs

See [CLAUDE.md](CLAUDE.md) for full setup, project structure, locator notes,
and how to add tests.
