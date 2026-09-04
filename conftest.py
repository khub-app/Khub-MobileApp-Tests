import os
import shutil
import subprocess

import openpyxl
import pytest

from utilities.driver_manager import DriverManager
from utilities.logger import get_logger
from utilities.report_metadata import write_environment_properties, write_executor_json
from utilities.screenshot_helper import take_screenshot

logger = get_logger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--env",
        action="store",
        default=None,
        help="Target environment defined in config/config.yaml (e.g. emulator, real_device)",
    )


# ------------------ Dynamic markers from Excel Tags sheet ------------------
# Mirrors khub-pos-tests' conftest.py: data/test_data.xlsx's "Tags" sheet has
# one row per test file (FilePath | smoke | regression | Date Added). A "Yes"
# in a marker column auto-applies that pytest marker to every item collected
# from that file, so `pytest -m smoke` / `-m regression` are driven by the
# spreadsheet instead of hardcoded decorators. New test file -> add a row
# there (exact relative path, matched as a path suffix) or it gets no markers.

def _load_tags_from_excel():
    """Read the Tags sheet and return {filepath: [marker_names]}."""
    excel_path = os.path.join(os.path.dirname(__file__), "data", "test_data.xlsx")
    if not os.path.exists(excel_path):
        return {}
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    if "Tags" not in wb.sheetnames:
        wb.close()
        return {}
    ws = wb["Tags"]
    headers = [cell.value for cell in ws[1]]
    marker_names = headers[1:]  # skip FilePath column
    tag_map = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        filepath = row[0]
        if not filepath:
            continue
        filepath = filepath.replace("\\", "/")
        markers = []
        for i, val in enumerate(row[1:]):
            if val and str(val).strip().lower() == "yes" and i < len(marker_names):
                markers.append(marker_names[i])
        if markers:
            tag_map[filepath] = markers
    wb.close()
    return tag_map


def pytest_collection_modifyitems(config, items):
    """Auto-apply markers from the Excel Tags sheet to collected test items."""
    tag_map = _load_tags_from_excel()
    if not tag_map:
        return
    applied_count = 0
    for item in items:
        item_path = str(item.fspath).replace("\\", "/")
        for tagged_path, markers in tag_map.items():
            if item_path.endswith(tagged_path):
                for marker_name in markers:
                    item.add_marker(getattr(pytest.mark, marker_name))
                applied_count += 1
                break
    if applied_count:
        print(f"\n[INFO] Applied Excel tags to {applied_count} test items from {len(tag_map)} tagged files")


# Holds whatever driver is currently active so the autouse screenshot fixture
# can reach it even though the `driver` fixture is class-scoped.
_active_driver = {"instance": None}


@pytest.fixture(scope="class")
def driver(request):
    env_name = request.config.getoption("--env")
    manager = DriverManager(env_name)
    manager.reset_app_data()  # every class starts logged out, regardless of run order
    driver_instance = manager.start_driver()
    _active_driver["instance"] = driver_instance
    yield driver_instance
    _active_driver["instance"] = None
    manager.stop_driver()


@pytest.fixture(autouse=True)
def _step_screenshot(request):
    """Attach a screenshot for every test method (pass or fail) to the Allure report."""
    yield
    driver_instance = _active_driver["instance"]
    if driver_instance is None:
        return

    rep_call = getattr(request.node, "rep_call", None)
    failed = bool(rep_call and rep_call.failed)
    try:
        import allure

        screenshot_path = take_screenshot(driver_instance, request.node.name)
        with open(screenshot_path, "rb") as image_file:
            allure.attach(
                image_file.read(),
                name="Failure Screenshot" if failed else "Screenshot",
                attachment_type=allure.attachment_type.PNG,
            )
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Could not capture step screenshot: {e}")


# Skip the remaining steps in a class once one step has failed - scenario test
# files are split into one method per logical UI step sharing state via class
# attributes, so a failed step must stop the rest from running against unknown
# app state while leaving unrelated classes untouched.
_class_failed_step = {}


def pytest_runtest_setup(item):
    cls = item.cls
    if cls is not None and cls in _class_failed_step:
        pytest.skip(f"Skipped: an earlier step in this class failed ({_class_failed_step[cls]})")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
    if report.when == "call" and report.failed and item.cls is not None:
        _class_failed_step[item.cls] = item.name


_run_stats = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}


def pytest_runtest_logreport(report):
    if report.when == "setup" and report.outcome == "failed":
        _run_stats["errors"] += 1
    elif report.when == "call":
        if report.outcome == "passed":
            _run_stats["passed"] += 1
        elif report.outcome == "failed":
            _run_stats["failed"] += 1
    if report.outcome == "skipped" and report.when in ("setup", "call"):
        _run_stats["skipped"] += 1


def pytest_sessionfinish(session, exitstatus):
    """Auto-generate the Allure HTML report from this run's results so a plain
    `pytest` invocation is enough - no separate `allure generate` step."""
    results_dir = session.config.getoption("--alluredir") or "reports/allure-results"
    if not os.path.isdir(results_dir) or not os.listdir(results_dir):
        return

    total = sum(_run_stats.values())
    stats = {"total": total, **_run_stats}
    try:
        write_environment_properties(results_dir, stats, session.config.getoption("--env"))
        write_executor_json(results_dir)
    except Exception as e:
        print(f"[WARNING] Could not write Allure environment/executor metadata: {e}")

    allure_cmd = shutil.which("allure")
    if not allure_cmd:
        print("\n[WARNING] Allure CLI not found on PATH - skipping report generation.")
        print(f"  To generate manually: allure generate {results_dir} -o reports/allure-report --clean --single-file")
        return

    report_dir = os.path.join(os.path.dirname(os.path.normpath(results_dir)), "allure-report")
    print("\n[INFO] Generating Allure HTML report...")
    try:
        result = subprocess.run(
            [allure_cmd, "generate", results_dir, "-o", report_dir, "--clean", "--single-file"],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as e:
        print(f"[WARNING] Allure generate failed to run: {e}")
        return

    if result.returncode == 0:
        print(f"[INFO] Allure report: {os.path.abspath(os.path.join(report_dir, 'index.html'))}")
    else:
        print(f"[WARNING] Allure generate failed (exit {result.returncode})")
        if result.stderr:
            print(f"  {result.stderr.strip()[:300]}")
