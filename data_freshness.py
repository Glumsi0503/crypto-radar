"""Separated freshness rules: historical research vs time-sensitive candidate alerts."""
import datetime as dt

UTC=dt.timezone.utc
RESEARCH_MAX_AGE_MIN=24*60
ACTIONABLE_MAX_AGE_MIN=40

def age_minutes(value,now):
    if not isinstance(value,str):raise ValueError("timestamp_required")
    stamp=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if stamp.tzinfo is None:raise ValueError("timezone_required")
    if now.tzinfo is None:raise ValueError("now_timezone_required")
    return (now.astimezone(UTC)-stamp.astimezone(UTC)).total_seconds()/60

def usable(value,now,max_age_min=RESEARCH_MAX_AGE_MIN):
    try:return 0<=age_minutes(value,now)<=max_age_min
    except (TypeError,ValueError,OverflowError):return False

def classification(value,now):
    if usable(value,now,ACTIONABLE_MAX_AGE_MIN):return "current"
    if usable(value,now,RESEARCH_MAX_AGE_MIN):return "historical_only"
    return "expired"
