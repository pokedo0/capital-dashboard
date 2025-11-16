from datetime import date, timedelta

RANGE_TO_DAYS = {
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
}


def resolve_range_end() -> date:
    return date.today()


def resolve_range_start(range_key: str) -> date:
    days = RANGE_TO_DAYS.get(range_key.upper())
    if not days:
        raise ValueError(f"Unsupported range '{range_key}'")
    return resolve_range_end() - timedelta(days=days)
