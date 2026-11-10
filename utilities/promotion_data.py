"""Reads the promotion-scenario test data khub-web-tests produces.

Mobile never calls the promotions API itself or creates promotion test data -
scripts/create_mobile_promotion_scenarios_api.py (run from khub-web-tests,
its own venv) creates fresh products/customer/promotion(s) for all 4
scenarios and writes them to one JSON file; this module just reads it. See
khub-web-tests/docs/mobile_promotion_api_handoff.md for the full data
contract (what each of the 4 scenarios - multi_tier, phase2_boundary,
repick, bxgy - contains and means).
"""
import json
import os
from functools import lru_cache

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SIBLING_ROOT = os.path.dirname(_REPO_ROOT)  # .../KhubAutomation
_WEB_TESTS_TESTDATA = os.path.join(_SIBLING_ROOT, "khub-web-tests", "testdata")


@lru_cache(maxsize=None)
def _load(env: str) -> dict:
    path = os.path.join(_WEB_TESTS_TESTDATA, f"mobile_promotion_scenarios_{env}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No promotion scenario data at {path}. Generate it first, from "
            f"khub-web-tests' own venv:\n"
            f"  python scripts/create_mobile_promotion_scenarios_api.py --env={env}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_scenario(name: str, env: str = "preprod") -> dict:
    """One scenario's dict - product(s)/customer/promotion id(s)+params.
    `name` is one of: multi_tier, phase2_boundary, repick, bxgy."""
    scenarios = _load(env)["scenarios"]
    if name not in scenarios:
        raise KeyError(f"Scenario {name!r} not in promotion data (env={env}); "
                        f"have: {list(scenarios)}")
    return scenarios[name]
