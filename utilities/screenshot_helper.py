from datetime import datetime
from pathlib import Path

SCREENSHOT_DIR = Path(__file__).resolve().parents[1] / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def take_screenshot(driver, name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    filepath = SCREENSHOT_DIR / f"{safe_name}_{timestamp}.png"
    driver.save_screenshot(str(filepath))
    return str(filepath)
