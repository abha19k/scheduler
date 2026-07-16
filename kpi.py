# kpi.py

import pandas as pd

from utils import minutes_to_hhmm


# =========================================================
# BUILD SCHEDULE DATAFRAME
# =========================================================

def build_schedule_dataframe(scheduled_ops):

    rows = []

    for op in scheduled_ops:

        due_end = op.DueDate + pd.Timedelta(days=1)

        slack_minutes = (
            due_end - op.EndTime
        ).total_seconds() / 60

        rows.append({

            # =============================================
            # ORDER INFO
            # =============================================

            "WorkOrderID": op.WorkOrderID,
            "OperationID": op.OperationID,
            "SequenceNumber": op.SequenceNumber,
            "OperationType": op.OperationType,

            # =============================================
            # MACHINE
            # =============================================

            "AssignedMachine": op.AssignedMachine,
            "BatchID": op.BatchID,

            # =============================================
            # PRODUCT
            # =============================================

            "ProductFamily": op.ProductFamily,
            "Color": op.Color,
            "Width": op.Width,
            "Weight": op.Weight,
            "Length": op.Length,
            "Temperature": op.Temperature,
            "Tool": op.Tool,

            # =============================================
            # TIMING
            # =============================================

            "DueDate": op.DueDate.strftime("%d-%b %H:%M"),

            "SetupStart": op.SetupStart,
            "ProductionStart": op.StartTime,
            "ProductionEnd": op.EndTime,

            "SetupStartDisplay": (
                op.SetupStart.strftime("%d-%b %H:%M")
                if op.SetupStart else None
                ),

            "ProductionStartDisplay": (
                op.StartTime.strftime("%d-%b %H:%M")
                if op.StartTime else None
                ),

            "ProductionEndDisplay": (
                op.EndTime.strftime("%d-%b %H:%M")
                if op.EndTime else None
                ),



            # =============================================
            # SLACK
            # =============================================

            "DueDateSlack": minutes_to_hhmm(slack_minutes),

            # =============================================
            # SETUP
            # =============================================

            "TotalSetupMinutes": round(op.SetupMinutes, 2),

            "FamilySetupMinutes": round(
                op.FamilySetupMinutes,
                2
            ),

            "WidthSetupMinutes": round(
                op.WidthSetupMinutes,
                2
            ),

            "TemperatureSetupMinutes": round(
                op.TemperatureSetupMinutes,
                2
            ),

            # =============================================
            # OVER-SOAK
            # =============================================

            "OverSoakMinutes": round(
                op.OverSoakMinutes,
                2
            ),

            "OverSoakViolation": op.OverSoakViolation,

            # =============================================
            # DELIVERY
            # =============================================

            "Late": op.Late,
            "LatePenalty": op.LatePenalty,
        })

    df = pd.DataFrame(rows)

    return df


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


# =========================================================
# OVERALL KPI
# =========================================================

# kpi.py




def build_kpi_dataframe(result):

    scheduled_ops = result["scheduled_ops"]
    machines = result["machines"]

    total_operations = len(scheduled_ops)

    late_operations = sum(
        1 for op in scheduled_ops
        if op.Late
    )

    delivery_performance = (
        (total_operations - late_operations)
        / total_operations
    ) * 100

    # =====================================================
    # TRUE MACHINE UTILIZATION
    # =====================================================

    total_machine_busy_hours = 0
    total_machine_available_hours = 0

    for machine in machines.values():

        if not machine.Timeline:
            continue

        machine_start = min(
            item["StartTime"]
            for item in machine.Timeline
        )

        machine_end = max(
            item["EndTime"]
            for item in machine.Timeline
        )

        available_hours = (
            machine_end - machine_start
        ).total_seconds() / 3600

        total_machine_available_hours += available_hours

        # -------------------------------------------------
        # Batch machine
        # Count merged occupied intervals only once
        # -------------------------------------------------

        if machine.MachineType.lower() == "batch":

            intervals = sorted([
                (
                    item["StartTime"],
                    item["EndTime"]
                )
                for item in machine.Timeline
            ])

            merged = []

            for start, end in intervals:

                if not merged:
                    merged.append([start, end])

                else:
                    last_start, last_end = merged[-1]

                    if start <= last_end:
                        merged[-1][1] = max(last_end, end)
                    else:
                        merged.append([start, end])

            busy_hours = sum(
                (
                    end - start
                ).total_seconds() / 3600
                for start, end in merged
            )

        # -------------------------------------------------
        # Regular machine
        # -------------------------------------------------

        else:

            busy_hours = sum(
                (
                    item["EndTime"] - item["StartTime"]
                ).total_seconds() / 3600
                for item in machine.Timeline
            )

        total_machine_busy_hours += busy_hours

    if total_machine_available_hours > 0:
        machine_utilization = (
            total_machine_busy_hours
            / total_machine_available_hours
        ) * 100
    else:
        machine_utilization = 0

    # =====================================================
    # TOTAL SCHEDULE HOURS
    # =====================================================

    all_start_times = [
        op.StartTime
        for op in scheduled_ops
        if op.StartTime is not None
    ]

    all_end_times = [
        op.EndTime
        for op in scheduled_ops
        if op.EndTime is not None
    ]

    if all_start_times and all_end_times:

        total_schedule_hours = (
            max(all_end_times)
            - min(all_start_times)
        ).total_seconds() / 3600

    else:
        total_schedule_hours = 0

    production_hours = sum(
        op.DurationHours
        for op in scheduled_ops
    )

    kpis = {
        "FeasibleSchedule":
            result["infeasible_count"] == 0,

        "InfeasibleCount":
            result["infeasible_count"],

        "OverSoakViolations":
            result["oversoak_violations"],

        "TotalOperations":
            total_operations,

        "LateOperations":
            late_operations,

        "DeliveryPerformancePercent":
            round(delivery_performance, 2),

        "LatePenalty":
            result["late_penalty"],

        "TotalSetupMinutes":
            round(result["setup"], 2),

        "FamilySetupMinutes":
            round(result["family_setup"], 2),

        "WidthSetupMinutes":
            round(result["width_setup"], 2),

        "TemperatureSetupMinutes":
            round(result["temperature_setup"], 2),

        "OvenUtilizationPercent":
            round(result["oven_utilization"], 2),

        "MachineUtilizationPercent":
            round(machine_utilization, 2),

        "ProductionHours":
            round(production_hours, 2),

        "TotalScheduleHours":
            round(total_schedule_hours, 2),

        "TotalCost":
            round(result["total_cost"], 2),
    }

    return pd.DataFrame([kpis])

