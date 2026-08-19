import pandas as pd

def _merge_intervals(
    intervals
):
    merged = []

    for start, end in sorted(intervals):
        if not merged:
            merged.append(
                [start, end]
            )
            continue

        last_end = merged[-1][1]

        if start <= last_end:
            merged[-1][1] = max(
                last_end,
                end
            )
        else:
            merged.append(
                [start, end]
            )

    return merged


def _calculate_busy_hours(
    machine
) -> float:
    intervals = [
        (
            item["StartTime"],
            item["EndTime"]
        )
        for item in machine.Timeline
    ]

    if not intervals:
        return 0.0

    if (
        machine.MachineType.lower() ==
        "batch"
    ):
        intervals = _merge_intervals(
            intervals
        )

    return sum(
        (
            end -
            start
        ).total_seconds() / 3600
        for start, end in intervals
    )


def calculate_oven_utilization(
    machines
) -> float:
    ovens = [
        machine
        for machine in machines.values()
        if (
            machine.MachineType.lower() ==
            "batch"
        )
    ]

    if not ovens:
        return 0.0

    all_intervals = [
        (
            item["StartTime"],
            item["EndTime"]
        )
        for oven in ovens
        for item in oven.Timeline
    ]

    if not all_intervals:
        return 0.0

    planning_start = min(
        start
        for start, _ in all_intervals
    )

    planning_end = max(
        end
        for _, end in all_intervals
    )

    planning_hours = (
        planning_end -
        planning_start
    ).total_seconds() / 3600

    if planning_hours <= 0:
        return 0.0

    total_busy_hours = sum(
        _calculate_busy_hours(oven)
        for oven in ovens
    )

    total_available_hours = (
        len(ovens) *
        planning_hours
    )

    return (
        total_busy_hours /
        total_available_hours
    ) * 100


def calculate_machine_utilization(
    machines
) -> float:
    machine_list = list(
        machines.values()
    )

    if not machine_list:
        return 0.0

    all_intervals = [
        (
            item["StartTime"],
            item["EndTime"]
        )
        for machine in machine_list
        for item in machine.Timeline
    ]

    if not all_intervals:
        return 0.0

    planning_start = min(
        start
        for start, _ in all_intervals
    )

    planning_end = max(
        end
        for _, end in all_intervals
    )

    planning_hours = (
        planning_end -
        planning_start
    ).total_seconds() / 3600

    if planning_hours <= 0:
        return 0.0

    total_busy_hours = sum(
        _calculate_busy_hours(machine)
        for machine in machine_list
    )

    total_available_hours = (
        len(machine_list) *
        planning_hours
    )

    if total_available_hours <= 0:
        return 0.0

    return (
        total_busy_hours /
        total_available_hours
    ) * 100


def calculate_resource_kpis(
    machines
) -> dict:
    return {
        "OvenUtilizationPercent":
            round(
                calculate_oven_utilization(
                    machines
                ),
                2
            ),

        "MachineUtilizationPercent":
            round(
                calculate_machine_utilization(
                    machines
                ),
                2
            ),
    }

def calculate_oven_idle_gap_hours(
    machines
) -> float:
    total_idle_gap_hours = 0.0

    ovens = [
        machine
        for machine in machines.values()
        if machine.MachineType.lower() == "batch"
    ]

    for oven in ovens:
        intervals = sorted(
            [
                (
                    item["StartTime"],
                    item["EndTime"]
                )
                for item in oven.Timeline
            ],
            key=lambda x: x[0]
        )

        if len(intervals) < 2:
            continue

        merged = _merge_intervals(
            intervals
        )

        for index in range(
            1,
            len(merged)
        ):
            previous_end = (
                merged[index - 1][1]
            )

            current_start = (
                merged[index][0]
            )

            gap_hours = (
                current_start -
                previous_end
            ).total_seconds() / 3600

            if gap_hours > 0:
                total_idle_gap_hours += (
                    gap_hours
                )

    return total_idle_gap_hours

def calculate_oven_load_imbalance(
    machines
) -> float:
    ovens = [
        machine
        for machine in machines.values()
        if machine.MachineType.lower() == "batch"
    ]

    if not ovens:
        return 0.0

    busy_hours = [
        _calculate_busy_hours(
            oven
        )
        for oven in ovens
    ]

    if not busy_hours:
        return 0.0

    average_load = (
        sum(busy_hours) /
        len(busy_hours)
    )

    return sum(
        abs(
            load -
            average_load
        )
        for load in busy_hours
    ) / len(busy_hours)

# =========================================================
# MACHINE KPI
# =========================================================

def build_machine_kpis(machines):

    rows = []

    for machine in machines.values():

        if not machine.Timeline:
            continue

        start = min(
            item["StartTime"]
            for item in machine.Timeline
        )

        end = max(
            item["EndTime"]
            for item in machine.Timeline
        )

        total_hours = (
            end - start
        ).total_seconds() / 3600

        busy_hours = 0

        setup_hours = 0

        for item in machine.Timeline:

            op = item["Operation"]

            duration = (
                item["EndTime"] -
                item["StartTime"]
            ).total_seconds() / 3600

            busy_hours += duration

            setup_hours += (
                op.SetupMinutes / 60
            )

        utilization = (
            (busy_hours / total_hours) * 100
            if total_hours > 0 else 0
        )

        rows.append({

            "MachineID": machine.MachineID,

            "MachineType": machine.MachineType,

            "Operations": len(machine.Timeline),

            "TotalScheduleHours": round(
                total_hours,
                2
            ),

            "BusyHours": round(
                busy_hours,
                2
            ),

            "SetupHours": round(
                setup_hours,
                2
            ),

            "UtilizationPercent": round(
                utilization,
                2
            ),
        })

    return pd.DataFrame(rows)