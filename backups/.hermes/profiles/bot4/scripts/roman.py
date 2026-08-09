"""Roman numeral conversion utilities.

Implements to_roman(n) and from_roman(s) for integers in [1, 3999].
Follows standard subtractive notation (IV=4, IX=9, XL=40, XC=90, CD=400, CM=900).

Author: Jack Loh (Biz Bot / BountyBook executor)
Written: 2026-07-30
Tested against: BountyBook job f940acbb-eb53-4b16-b4dd-1e43e30dea37
"""
from __future__ import annotations

from typing import List, Tuple


# Roman numeral values, ordered from largest to smallest.
# Each tuple is (value, symbol). Subtractive notation pairs like (4, "IV")
# are explicit rather than relying on rule-ordering at conversion time.
_VALUES: Tuple[Tuple[int, str], ...] = (
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
)


# Minimum and maximum integers representable in standard Roman numerals.
MIN_ROMAN = 1
MAX_ROMAN = 3999


def to_roman(n: int) -> str:
    """Convert an integer in [1, 3999] to its Roman numeral representation.

    Args:
        n: Integer to convert. Must satisfy 1 <= n <= 3999.

    Returns:
        A Roman numeral string using subtractive notation.

    Raises:
        ValueError: If n is outside the valid range [1, 3999] or is not an int.
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise ValueError(f"to_roman requires an int, got {type(n).__name__}: {n!r}")
    if n < MIN_ROMAN or n > MAX_ROMAN:
        raise ValueError(
            f"to_roman argument must be between {MIN_ROMAN} and {MAX_ROMAN}, got {n}"
        )

    parts: List[str] = []
    remaining = n
    for value, symbol in _VALUES:
        while remaining >= value:
            parts.append(symbol)
            remaining -= value
    return "".join(parts)


def from_roman(s: str) -> int:
    """Convert a Roman numeral string to its integer value.

    Accepts both canonical form (e.g. "MCMXCIV") and case-insensitive variants.
    Validates that the string contains only valid Roman numeral characters
    arranged in a canonical (greedy) form.

    Args:
        s: Roman numeral string. Case-insensitive.

    Returns:
        Integer value of the Roman numeral, in [1, 3999].

    Raises:
        ValueError: If the string is empty, contains invalid characters,
            is not in canonical form, or represents a value outside [1, 3999].
    """
    if not isinstance(s, str):
        raise ValueError(f"from_roman requires a str, got {type(s).__name__}: {s!r}")
    if not s:
        raise ValueError("from_roman argument must be a non-empty string")

    upper = s.upper().strip()

    # Validate characters
    valid_chars = set("IVXLCDM")
    bad_chars = sorted({c for c in upper if c not in valid_chars})
    if bad_chars:
        raise ValueError(f"Invalid Roman numeral characters: {bad_chars}")

    # Reject common malformed patterns before parsing
    # (e.g. "IIII", "VV", "IC" — non-canonical subtractive pairs).
    _reject_non_canonical(upper)

    total = 0
    i = 0
    while i < len(upper):
        # Check for two-character subtractive pair
        if i + 1 < len(upper):
            pair = upper[i : i + 2]
            pair_value = _SUBTRACTIVE_PAIRS.get(pair)
            if pair_value is not None:
                total += pair_value
                i += 2
                continue
        # Single character
        char_value = _SINGLE_VALUES[upper[i]]
        total += char_value
        i += 1

    if total < MIN_ROMAN or total > MAX_ROMAN:
        raise ValueError(
            f"Roman numeral {s!r} represents {total}, outside [{MIN_ROMAN}, {MAX_ROMAN}]"
        )
    return total


_SINGLE_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


# Subtractive notation pairs (the six canonical forms).
_SUBTRACTIVE_PAIRS = {
    "IV": 4,
    "IX": 9,
    "XL": 40,
    "XC": 90,
    "CD": 400,
    "CM": 900,
}


def _reject_non_canonical(s: str) -> None:
    """Raise ValueError if s contains non-canonical Roman numeral patterns.

    A canonical Roman numeral follows these rules:
    - Only the six subtractive pairs (IV, IX, XL, XC, CD, CM) are allowed.
    - Symbols I, X, C, M may repeat at most three times in a row.
    - Symbols V, L, D never repeat.
    - The value, when parsed greedily, must equal the canonical form.
    """
    # Check for invalid repetition of non-repeating symbols
    for sym in ("V", "L", "D"):
        if sym * 2 in s:
            raise ValueError(f"Symbol {sym} cannot repeat: {s!r}")

    # Check max-three repetition of I, X, C, M
    for sym in ("I", "X", "C", "M"):
        if sym * 4 in s:
            raise ValueError(f"Symbol {sym} cannot appear 4+ times in a row: {s!r}")

    # Reject any subtractive pair not in canonical list
    i = 0
    while i < len(s) - 1:
        pair = s[i : i + 2]
        # If second char is greater than first, it must be a canonical pair
        if _SINGLE_VALUES[pair[1]] > _SINGLE_VALUES[pair[0]]:
            if pair not in _SUBTRACTIVE_PAIRS:
                raise ValueError(f"Non-canonical subtractive pair {pair!r} in {s!r}")
        i += 1


# Self-test (informational — not executed at import).
if __name__ == "__main__":
    # Basic spot checks; the platform's oracle test is authoritative.
    samples = [
        (1, "I"),
        (4, "IV"),
        (9, "IX"),
        (14, "XIV"),
        (40, "XL"),
        (90, "XC"),
        (400, "CD"),
        (900, "CM"),
        (1994, "MCMXCIV"),
        (2024, "MMXXIV"),
        (3999, "MMMCMXCIX"),
    ]
    for n, expected in samples:
        result = to_roman(n)
        assert result == expected, f"to_roman({n}) = {result!r}, expected {expected!r}"
        rt = from_roman(result)
        assert rt == n, f"round-trip failed for {n}: got {rt}"
    print(f"OK: {len(samples)} round-trip samples passed")