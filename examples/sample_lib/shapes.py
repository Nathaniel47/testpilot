"""A tiny sample library used to demonstrate the TestPilot GitHub Action."""


def clamp(value: int, low: int, high: int) -> int:
    """Limit value to the range [low, high].

    >>> clamp(5, 0, 3)
    3
    >>> clamp(-2, 0, 3)
    0
    >>> clamp(2, 0, 3)
    2
    """
    if value < low:
        return low
    if value > high:
        return high
    return value


def is_leap_year(year: int) -> bool:
    """Gregorian leap year rule.

    >>> is_leap_year(2024)
    True
    >>> is_leap_year(1900)
    False
    """
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
