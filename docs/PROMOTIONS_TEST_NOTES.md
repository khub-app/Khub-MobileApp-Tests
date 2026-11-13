# Promotions — Quick Reference

9 test files, `pytest.ini` marker `promotion`, all registered in the Tags
sheet (`scripts/gen_test_data_xlsx.py` → `data/test_data.xlsx`). Each file
is one class, one `test_NN_*` per UI step (fails fast — later steps skip if
an earlier one fails). All build a fresh Online sale, pay Cash in full, and
validate through Cart Summary → Sales History → View Details unless noted.

Data comes from `khub-web-tests/scripts/create_mobile_promotion_scenarios_api.py`
(run there first to refresh `mobile_promotion_scenarios_<env>.json`) — mobile
never creates promotions/products itself.

Run one file:
`venv\Scripts\python.exe -m pytest tests/promotions/<file> -v`

Run all:
`venv\Scripts\python.exe -m pytest tests/promotions/ -v -m promotion`

---

### 1. Single Promotion Applied Across All Packaging Tiers (Piece / Pack / Case / Pallet)
- **File**: `tests/promotions/test_promotion_multi_tier.py`
- **Test data**: `multi_tier`
- **Description**: checks that one quantity-range promotion discounts a
  product consistently no matter which packaging tier it is sold in. The
  same product's 4 tiers (Piece, Pack, Case, Pallet) are added to one cart
  as 4 separate lines, but only the Piece tier's quantity actually falls
  inside the promotion's qualifying range — so this also proves the app
  does NOT discount a tier just because a sibling tier of the same product
  happens to be discounted.
- **Steps**: load scenario → open Create Sale Order → customer/order info
  → add Piece at qty_min (in-range) then Pack/Case/Pallet via "Add another
  unit" (each fixed qty=1 by the app) → validate Cart Summary → pay Cash →
  validate Sales History → View Details.
- **Validation**: Piece line shows the promo banner + discounted price
  pair; the qty=1 Pack/Case/Pallet lines are below range and show no
  discount; Cart Summary's Sub Total/Promo Savings/Grand Total; View
  Details' non-discounted tier lines (the discounted line's "Extended"
  field is a known app bug — logged as a warning, not asserted).

### 2. Discount Switches On/Off Exactly at the Quantity-Range Boundaries
- **File**: `tests/promotions/test_promotion_phase2_boundary.py`
- **Test data**: `phase2_boundary`
- **Description**: checks that a promotion's discount is a strict on/off
  boundary tied to its configured minimum and maximum quantity — never a
  gradual or partial discount. The same product is added at 5 different
  quantities (1, 2, 3, 5, 6) across separate attempts to prove the discount
  is absent just outside the range and present everywhere inside it,
  including exactly at both edges.
- **Steps**: load scenario → try qty 1 (below min, discard order) → qty 3
  (mid-range, discard) → qty 5 (at max, discard) → qty 6 (above max,
  discard) → qty 2 (at min — this one is kept) → Cart Summary → pay Cash →
  Sales History → View Details.
- **Validation**: no discount at qty 1/6; discount present at qty 2/3/5;
  the final qty=2 order's totals end-to-end.

### 3. Two Overlapping Promotions on the Same Product — Highest Discount Wins
- **File**: `tests/promotions/test_promotion_repick.py`
- **Test data**: `repick`
- **Description**: checks that when two separate promotions both qualify
  for the same product at the same time, the app automatically applies
  whichever one gives the bigger discount — with no manual picker or
  switch for the user to choose between them (confirmed no such UI exists
  on this app).
- **Steps**: load scenario → open order → customer/order info → add
  product at qualifying qty → Cart Summary → pay Cash → Sales History →
  View Details.
- **Validation**: the line discounts at the HIGHER of the two configured
  percentages; Cart Summary and View Details totals match that higher
  discount.

### 4. Buy-X-Get-Y: Reward Product Discounts Only After the Trigger Quantity Is Met
- **File**: `tests/promotions/test_promotion_bxgy.py`
- **Test data**: `bxgy`
- **Description**: checks the core Buy-X-Get-Y mechanic: a "reward"
  product only becomes discounted once a separate "trigger" product
  reaches its required quantity in the same cart. Also checks that a
  reward line already sitting in the cart re-evaluates live the moment the
  trigger threshold is crossed, without needing to be removed and
  re-added.
- **Steps**: add reward product first (plain) → add trigger below
  trigger_qty (reward still plain) → push trigger to meet trigger_qty
  (reward discounts live, no re-add needed) → Cart Summary → pay Cash →
  Sales History → View Details.
- **Validation**: reward line is plain until trigger qty is met, then
  shows the discount; Cart Summary's Promo Savings reflects only the
  reward's discount.

### 5. Buy-X-Get-Y: Reward Discount Has a Hard Cutoff at Its Maximum Quantity
- **File**: `tests/promotions/test_promotion_buy3_get2.py`
- **Test data**: `buy3_get2_half_off` (trigger_qty=3, max_reward_qty=2,
  50% off)
- **Description**: checks that a Buy-X-Get-Y reward's discount is capped
  at a fixed maximum quantity, and that going even one unit over that cap
  removes the discount from the WHOLE line rather than discounting only up
  to the cap (buy 3 of the trigger product, get up to 2 units of the
  reward product at 50% off).
- **Steps**: add reward at qty > max_reward_qty first with trigger met
  (confirm NO discount at all) → fresh order: add reward at exactly
  max_reward_qty before trigger (plain) → add trigger below trigger_qty
  (still plain) → push trigger to meet trigger_qty (reward fully
  discounts) → Cart Summary → pay Cash → Sales History → View Details.
- **Validation**: reward qty over the max gets zero discount even with
  trigger met (no partial); reward qty at/under the max gets full 50% off
  once triggered; Cart Summary discount covers exactly max_reward_qty
  units.

### 6. Multiple Independent Promotions Combined in a Single Order
- **File**: `tests/promotions/test_promotion_multi_promo_cart.py`
- **Test data**: reuses 3 existing scenarios' products (no new data)
- **Description**: checks that Cart Summary's "Promo Savings" total
  correctly adds up several different, unrelated promotions that are all
  active at once in the same cart (3 independent promotions spread across
  4 lines), rather than only reflecting whichever one was applied most
  recently.
- **Steps**: load 3 scenarios' data → open order → customer/order info →
  add all 4 lines (covering the 3 independent promotions) and validate
  each → Cart Summary → pay Cash → Sales History → View Details.
- **Validation**: each line's own discount is correct; Cart Summary's
  Promo Savings equals the exact sum of all 3 lines' individual discounts.

### 7. Manual Additional Discount Stacks Cleanly on Top of an Active Promotion
- **File**: `tests/promotions/test_promotion_additional_discount_stacking.py`
- **Test data**: `multi_tier` (reused), manual discount = $30.00
- **Description**: checks that the app's own manual "Additional Discount"
  field on Cart Summary is fully independent of promotion-engine
  discounting. Applying a manual discount on top of an already-promoted
  order should reduce only the Grand Total by the exact manual amount,
  without changing or doubling the promotion's own discount.
- **Steps**: add the promoted product in-range, validate the promo →
  capture the promo-only Cart Summary → apply the $30 Additional Discount →
  validate Sub Total/Promo Savings are UNCHANGED and Grand Total drops by
  exactly $30 → pay Cash → Sales History → View Details.
- **Validation**: Promo Savings and discounted Sub Total stay identical
  before/after; Grand Total reduces by exactly the manual discount amount.

### 8. Promotion Outside Its Active Date Range Gives No Discount
- **File**: `tests/promotions/test_promotion_validity_window.py`
- **Test data**: `validity_window` (one `not_started` promo, one `expired`
  promo, 2 separate products)
- **Description**: checks that a promotion configured with a start/end
  date outside today's date applies zero discount and leaves no visual
  trace at all on the cart line — covering both a promotion that hasn't
  started yet and one that has already ended.
- **Steps**: load scenario → open order → customer/order info → add both
  products at a qualifying qty → Cart Summary → pay Cash → Sales History.
- **Validation**: neither product's line shows any promo banner/price
  pair/range indicator; Cart Summary has no "Promo Savings" row at all;
  Grand Total is full, undiscounted price; Sales History shows the same
  full totals.

### 9. Promotion Restricted to a Specific Customer Group
- **File**: `tests/promotions/test_promotion_customer_targeting.py`
- **Test data**: `customer_targeting` (promo scoped to Customer Group id=3
  — a STABLE, manually-provisioned fixture, not regenerated per run; see
  the scenario's own builder docstring in
  `create_mobile_promotion_scenarios_api.py` if it's ever lost)
- **Description**: checks that a promotion scoped to a specific Customer
  Group only discounts orders for customers who belong to that group. The
  identical product and quantity is tried for a customer outside the group
  (expect full price, no discount) and a customer inside the group (expect
  the discount to apply).
- **Steps**: load scenario (resolve product SKU, both customers) →
  out-of-group customer: add product, confirm NO discount (no order kept)
  → in-group customer: open a real order, add same product/qty, confirm
  discount applies → Cart Summary → pay Cash → Sales History.
- **Validation**: out-of-group customer's line is fully plain; in-group
  customer's line discounts; Cart Summary and Sales History reflect the
  in-group order's discounted totals.

---

## Known app behaviors these tests assert on purpose (not bugs in the tests)

- Self-referential BXGY (trigger == reward product/unit) never discounts —
  not covered by a dedicated test; `buy3_get2_half_off`/`bxgy` are built
  cross-product specifically because of this.
- View Details' per-line "Extended" field is wrong for a discounted line
  (applies the discount with the wrong sign, ignores qty) — `multi_tier`
  logs a warning instead of asserting on it.
- No cart line can be edited or qty-changed once placed; "Order Qty *" on
  an existing line is read-only. `phase2_boundary` works around this with
  `discard_order()` (Android back → "Go Back") between attempts.
- Re-adding the same SKU+UPC merges into the existing cart line (qty
  increments) instead of duplicating — `bxgy`/`buy3_get2` use this to cross
  the trigger threshold live.

## Not automated (investigated, blocked on a missing prerequisite)

**Sales Return of a promoted order** — the Return action only appears once
an order reaches **Completed** status on the web portal; mobile Fulfillment
only drives orders to Packed, and no API shortcut to force Completed was
found. See `pages/sales_return_page.py` docstring and the "Sales Return"
section of `CLAUDE.md` for full findings and how to unblock it later.
