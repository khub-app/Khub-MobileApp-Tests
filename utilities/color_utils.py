"""Hex/RGB color comparison helpers, for visually verifying a rendered
color (e.g. a Label Management chip's configured background/text color)
that content-desc text alone can't carry - see BasePage.get_element_color.
"""


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def colors_close(actual_rgb, expected_hex: str, tolerance: int = 35) -> bool:
    """True if `actual_rgb` (an (r,g,b[,a]) tuple, e.g. from a screenshot
    pixel sample) is within `tolerance` per channel of `expected_hex`.
    A nonzero tolerance is needed because anti-aliasing, JPEG-free but
    still lossy scaling, and sub-pixel sampling position all shift the
    sampled pixel slightly off the exact configured color."""
    er, eg, eb = hex_to_rgb(expected_hex)
    ar, ag, ab = actual_rgb[0], actual_rgb[1], actual_rgb[2]
    return abs(ar - er) <= tolerance and abs(ag - eg) <= tolerance and abs(ab - eb) <= tolerance
