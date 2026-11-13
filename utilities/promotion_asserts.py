"""Shared assertion helper for promotion-engine cart-line checks.

Exists because a cart line's discount state can be wrong for two very
different reasons that look identical from inside a single test: a real
app/automation bug, or a stray promotion on the shared preprod tenant
bleeding onto this line. Confirmed live 2026-11-11: a promotion named
"new years" was built by selecting a large, unfiltered batch of products
in the portal's own "Add Sources" picker (not a "whole catalog" toggle -
see CLAUDE.md's "Shared-tenant promotion contamination" note) and ended up
covering ~100 products including several of this suite's own scenario
products, discounting them in tests that expected no discount at all.
Every promotion this suite creates is named "Mobile_..." - any other name
showing up as the active promo on a line is the signature of this same
class of problem recurring.
"""

PORTAL_URL = "preprod.ikhub.biz"


def assert_promo_state(line: dict, expected_active: bool, context: str = "") -> None:
    """Assert a cart line's is_promo_active matches what the test expects.

    On mismatch, raises with the full line for debugging. When the line
    is unexpectedly discounted (expected_active=False but a promo is
    live), the message also says whether that promo is one of ours
    ("Mobile_..." - a real bug worth investigating here) or not (almost
    certainly shared-tenant contamination - go delete the stray promotion
    in Marketing > Promotions on the web portal instead of debugging this
    test further).
    """
    actual = bool(line.get("is_promo_active"))
    if actual == expected_active:
        return

    base = (
        f"{context}expected is_promo_active={expected_active}, got {actual} "
        f"(promo={line.get('promo_name')!r}, {line.get('promo_percent')}% off). "
        f"Full line: {line}"
    )
    if not (actual and not expected_active):
        raise AssertionError(base)

    own_promo = str(line.get("promo_name") or "").startswith("Mobile_")
    if own_promo:
        hint = (
            "This IS one of our own 'Mobile_' scenario promotions, so this "
            "looks like a real app or automation bug, not shared-tenant "
            "contamination - investigate here first."
        )
    else:
        hint = (
            f"'{line.get('promo_name')}' is NOT one of our own scenario "
            "promotions (ours are always named 'Mobile_...'). This is almost "
            "certainly a stray, broadly-scoped promotion on the shared "
            f"preprod tenant bleeding onto this product. Check Marketing > "
            f"Promotions on {PORTAL_URL} for a promo covering SKU "
            f"{line.get('sku')} that isn't one of ours, and delete it there "
            "rather than treating this as a test/app bug."
        )
    raise AssertionError(f"{base}\n{hint}")
