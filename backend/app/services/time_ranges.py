from datetime import date, timedelta

RANGE_TO_DAYS = {
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "5Y": 365 * 5,
}


def resolve_range_end() -> date:
    return date.today()


def resolve_range_start(range_key: str) -> date:
    key = range_key.upper()
    if key == "YTD":
        today = date.today()
        return date(today.year, 1, 1)
    days = RANGE_TO_DAYS.get(key)
    if not days:
        raise ValueError(f"Unsupported range '{range_key}'")
    return resolve_range_end() - timedelta(days=days)
