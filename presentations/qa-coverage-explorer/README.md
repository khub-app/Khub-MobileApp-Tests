# Mobile QA Coverage Explorer

A standalone, clickable one-page summary of what this suite automates — built for sharing with leadership/stakeholders, not part of the test run itself.

Mirrors the format of the `khub-web-tests` QA Coverage Explorer at
`../../khub-web-tests/presentations/qa-coverage-explorer/` — same layout, same
theming, same module/panel pattern — but kept as its own file here rather than
appended to that one, since it covers a different app and a different repo.

## What it is

Open `index.html` directly in a browser (no server needed — it's a single self-contained file, no external dependencies). Click a module on the left to see its real coverage areas on the right.

- Light/dark mode aware (follows the OS theme automatically)
- Works down to phone width
- Pure HTML/CSS/vanilla JS — no build step, no dependencies

## Updating it

This file is also published as a Claude artifact at:
`https://claude.ai/artifact/YEEAf64RitDCTkHVcSsXK8`

When coverage changes (a new module, a new test step, an updated module count), update the `DATA` object near the bottom of `index.html` — each module is a `{name, count, rich, items}` entry; `rich: true` items are `[title, description]` pairs pulled from the real `@allure.title`/assertions in the test file, not a paraphrase. Keep `count` in sync with `items.length`.

## Last updated

2026-10-26 — Created. 2 modules: Login & Authentication (`tests/login/test_login.py`, 2 scenarios) and Online Sale + Fulfillment E2E (`tests/fulfillment/test_online_sale_fulfillment.py`, 12 steps — API test-data prep through Cash payment, Sales History/View Details validation, Assign, Pick, Pack and the Packed section). Coverage bullets sourced directly from the two test files' `@allure.title`s and assertions.
