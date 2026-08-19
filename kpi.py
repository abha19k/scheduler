# kpi.py

import pandas as pd

from utils import minutes_to_hhmm

from kpi_engine import (
    calculate_delivery_kpis,
    calculate_resource_kpis,
    calculate_schedule_kpis,
    build_machine_kpis,
)


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
# SETUP KPIS
# =========================================================

def calculate_setup_kpis(result):

    return {
        "TotalSetupMinutes":
            round(
                result["setup"],
                2
            ),

        "FamilySetupMinutes":
            round(
                result["family_setup"],
                2
            ),

        "WidthSetupMinutes":
            round(
                result["width_setup"],
                2
            ),

        "TemperatureSetupMinutes":
            round(
                result["temperature_setup"],
                2
            ),
    }


# =========================================================
# CONSTRAINT KPIS
# =========================================================

def calculate_constraint_kpis(result):

    return {
        "FeasibleSchedule":
            result["infeasible_count"] == 0,

        "InfeasibleCount":
            result["infeasible_count"],

        "OverSoakViolations":
            result["oversoak_violations"],
    }


# =========================================================
# OVERALL KPI
# =========================================================

def build_kpi_dataframe(result):

    scheduled_ops = (
        result["scheduled_ops"]
    )

    machines = (
        result["machines"]
    )

    delivery_kpis = (
        calculate_delivery_kpis(
            scheduled_ops
        )
    )

    schedule_kpis = (
        calculate_schedule_kpis(
            scheduled_ops
        )
    )

    resource_kpis = (
        calculate_resource_kpis(
            machines
        )
    )

    setup_kpis = (
        calculate_setup_kpis(
            result
        )
    )

    constraint_kpis = (
        calculate_constraint_kpis(
            result
        )
    )

    kpis = {
        **constraint_kpis,
        **delivery_kpis,
        **schedule_kpis,
        **resource_kpis,
        **setup_kpis,

        "LatePenalty":
            result["late_penalty"],


        "TotalCost":
            round(
                result["total_cost"],
                2
            ),
    }

    return pd.DataFrame(
        [kpis]
    )







