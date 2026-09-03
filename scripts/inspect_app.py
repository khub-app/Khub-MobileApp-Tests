"""Ad-hoc UI inspector: launches the admin app via Appium (clearing app data
first so it starts on the Login screen), then dumps the current screen's XML
page source and a screenshot into scripts/_inspect/ for locator authoring.

Usage:
    venv\\Scripts\\python.exe scripts/inspect_app.py [--env emulator] [--no-clear] [tag]

`tag` is an optional filename suffix so successive dumps don't overwrite
(e.g. `... inspect_app.py after-login`).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utilities.driver_manager import DriverManager  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "_inspect"
OUT_DIR.mkdir(exist_ok=True)


def main():
    args = [a for a in sys.argv[1:]]
    env = None
    clear = True
    tag = "screen"
    if "--no-clear" in args:
        clear = False
        args.remove("--no-clear")
    if "--env" in args:
        i = args.index("--env")
        env = args[i + 1]
        del args[i:i + 2]
    if args:
        tag = args[0]

    manager = DriverManager(env)
    if clear:
        manager.reset_app_data()
    driver = manager.start_driver()
    try:
        input(f"\nApp launched. Navigate to the screen you want, then press Enter to dump '{tag}'... ")
        (OUT_DIR / f"{tag}.xml").write_text(driver.page_source, encoding="utf-8")
        driver.save_screenshot(str(OUT_DIR / f"{tag}.png"))
        print(f"Wrote {OUT_DIR / (tag + '.xml')} and {tag}.png")
    finally:
        manager.stop_driver()


if __name__ == "__main__":
    main()
