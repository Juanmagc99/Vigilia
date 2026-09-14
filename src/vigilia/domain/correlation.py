from datetime import datetime, timedelta


SEVERITY_RANK = {"unknown": 0, "info": 1, "warning": 2, "critical": 3}


def correlation_cutoff(received_at: datetime, window_minutes: int) -> datetime:
    return received_at - timedelta(minutes=window_minutes)


def highest_severity(current: str, incoming: str) -> str:
    if SEVERITY_RANK.get(incoming, 0) > SEVERITY_RANK.get(current, 0):
        return incoming
    return current


def should_resolve(latest_statuses: dict[str, str]) -> bool:
    return bool(latest_statuses) and all(
        status == "resolved" for status in latest_statuses.values()
    )
