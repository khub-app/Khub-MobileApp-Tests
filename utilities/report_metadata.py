import json
import os
import platform
import socket
from datetime import datetime

from config.config_reader import ConfigReader


def write_environment_properties(results_dir: str, stats: dict, env_name: str | None = None):
    """Writes Allure's environment.properties file into the results dir - a
    plain Allure convention (any *.properties file there populates the
    report's Environment widget)."""
    env_config = ConfigReader().get_environment(env_name)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = stats.get("total", 0)
    passed = stats.get("passed", 0)
    pass_pct = f"{(passed / total * 100):.1f}%" if total else "N/A"

    props = [
        ("Environment", env_name or "emulator"),
        ("Backend\\ Tenant", "preprod"),
        ("Device", env_config.get("device_name", "unknown")),
        ("App\\ Package", env_config.get("app_package", "unknown")),
        ("Android\\ Version", str(env_config.get("platform_version", "unknown"))),
        ("Host\\ Platform", f"{platform.system()} {platform.release()}"),
        ("Timestamp", timestamp),
        ("Total\\ Test\\ Cases\\ Executed", str(total)),
        ("Tests\\ Passed", str(passed)),
        ("Tests\\ Failed", str(stats.get("failed", 0))),
        ("Tests\\ Skipped", str(stats.get("skipped", 0))),
        ("Setup\\ Errors", str(stats.get("errors", 0))),
        ("Test\\ Pass\\ Percentage", pass_pct),
    ]

    env_file = os.path.join(results_dir, "environment.properties")
    with open(env_file, "w", encoding="utf-8") as f:
        for key, value in props:
            f.write(f"{key}={value}\n")


def write_executor_json(results_dir: str):
    """Writes Allure's executor.json into the results dir - populates the
    report's Executors widget (who ran it, when)."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    executor_data = {
        "name": os.environ.get("USERNAME") or socket.gethostname(),
        "type": "local",
        "buildName": f"Local Run - {timestamp}",
        "buildOrder": int(datetime.now().timestamp()),
        "reportName": "khub-mobileApp-tests Allure Report",
    }
    executor_file = os.path.join(results_dir, "executor.json")
    with open(executor_file, "w", encoding="utf-8") as f:
        json.dump(executor_data, f, indent=2)
