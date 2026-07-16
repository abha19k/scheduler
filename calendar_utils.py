# calendar_utils.py

from datetime import datetime, timedelta
from typing import Dict, List

from models import CalendarDetail, Machine


# =========================================================
# CHECK IF MACHINE IS AVAILABLE
# =========================================================

def is_machine_available(
    machine: Machine,
    calendar_details: Dict[str, List[CalendarDetail]],
    dt: datetime
) -> bool:

    if not machine.CalendarIDs:
        return True

    weekday_name = dt.strftime("%A")
    current_time = dt.time()
    current_date = dt.date()

    all_rules = []

    for calendar_id in machine.CalendarIDs:
        rules = calendar_details.get(calendar_id, [])
        all_rules.extend(rules)

    # =====================================================
    # SPECIFIC DATE RULES
    # =====================================================

    for rule in all_rules:
        if rule.RuleType.lower() != "date":
            continue

        if rule.SpecificDate is None:
            continue

        if rule.SpecificDate.date() != current_date:
            continue

        if rule.IsUnavailable:
            return False

        if (
            rule.AvailableStartTime is not None
            and rule.AvailableEndTime is not None
        ):
            return (
                rule.AvailableStartTime
                <= current_time
                < rule.AvailableEndTime
            )

    # =====================================================
    # WEEKLY RULES
    # =====================================================

    weekly_rules = [
        r for r in all_rules
        if r.RuleType.lower() == "weekly"
    ]

    if not weekly_rules:
        return True

    matched_weekday_rules = [
        r for r in weekly_rules
        if (r.Weekday or "").lower() == weekday_name.lower()
    ]

    if not matched_weekday_rules:
        return False

    for rule in matched_weekday_rules:

        if rule.IsUnavailable:
            return False

        if (
            rule.AvailableStartTime is not None
            and rule.AvailableEndTime is not None
        ):

            if (
                rule.AvailableStartTime
                <= current_time
                < rule.AvailableEndTime
            ):
                return True

    return False


# =========================================================
# FIND NEXT AVAILABLE TIME
# =========================================================

def next_available_time(
    machine: Machine,
    calendar_details: Dict[str, List[CalendarDetail]],
    dt: datetime
) -> datetime:

    current = dt

    # Search minute-by-minute
    # industrial APS simplification

    for _ in range(60 * 24 * 365):

        if is_machine_available(
            machine,
            calendar_details,
            current
        ):
            return current

        current += timedelta(minutes=1)

    raise ValueError(
        f"Could not find available calendar slot for {machine.MachineID}"
    )


# =========================================================
# ENSURE FULL OPERATION FITS
# =========================================================

def adjust_to_calendar(
    machine: Machine,
    calendar_details: Dict[str, List[CalendarDetail]],
    proposed_start: datetime,
    duration_hours: float
):

    current_start = next_available_time(
        machine,
        calendar_details,
        proposed_start
    )

    duration_minutes = int(duration_hours * 60)

    while True:

        feasible = True

        for minute in range(duration_minutes):

            current_time = current_start + timedelta(minutes=minute)

            if not is_machine_available(
                machine,
                calendar_details,
                current_time
            ):
                feasible = False
                break

        if feasible:
            return current_start

        current_start = next_available_time(
            machine,
            calendar_details,
            current_start + timedelta(minutes=1)
        )