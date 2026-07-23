# backend/optimizer_service.py

import sys
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
from typing import Dict, Any, List
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from data_loader import load_scheduling_input
from genetic_algorithm import run_ga
from kpi import (
    build_schedule_dataframe,
    build_kpi_dataframe,
    build_machine_kpis,
)
from gantt import create_gantt_chart

from models import (
    Scenario,
    ScenarioKPI,
    PlannedTask,
    ScenarioDefinition,
)

from scenario_engine import (
    create_scenario,
    add_planned_task,
    create_default_scenarios,
    apply_scenario_definition,
)

from backend.scenario_excel_store import save_scenario_result_to_excel


OUTPUT_DIR = BASE_DIR / "backend" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def serialize_datetime(value):
    if value is None:
        return None
    return str(value)


def serialize_planned_task(task: PlannedTask) -> dict:
    data = asdict(task)

    data["SetupStart"] = serialize_datetime(task.SetupStart)
    data["StartTime"] = serialize_datetime(task.StartTime)
    data["EndTime"] = serialize_datetime(task.EndTime)
    data["CreatedDate"] = serialize_datetime(task.CreatedDate)
    data["UpdatedDate"] = serialize_datetime(task.UpdatedDate)
    data["HeatingEndTime"] = serialize_datetime(task.HeatingEndTime)
    data["ReleaseTime"] = serialize_datetime(task.ReleaseTime)
    data["BatchEndTime"] = serialize_datetime(task.BatchEndTime)

    return data


def serialize_scenario(scenario: Scenario) -> dict:
    return {
        "ScenarioID": scenario.ScenarioID,
        "ScenarioName": scenario.ScenarioName,
        "CreatedBy": scenario.CreatedBy,
        "CreatedDate": serialize_datetime(scenario.CreatedDate),
        "BaseScenarioID": scenario.BaseScenarioID,
        "IsManualScenario": scenario.IsManualScenario,
        "CalendarID": scenario.CalendarID,
        "PlannerNotes": scenario.PlannerNotes,
        "Status": scenario.Status,
    }


def apply_custom_parameter_overrides(
    scenario_input,
    custom_parameter_overrides: Dict[str, Any] | None
):
    if not custom_parameter_overrides:
        return

    allowed_parameters = {
        "WidthSetupPerUnit",
        "LateOrderPenalty",
        "PopulationSize",
        "Generations",
        "MutationRate",
        "EliteSize",
        "TournamentSize",
        "TemperatureSetupPer10DegreeMinutes",
        "MaximumAllowedGapBetweenHeatingAndPressHours",
        "MaxOverSoakMinutes",
    }

    for key, value in custom_parameter_overrides.items():
        if key not in allowed_parameters:
            continue

        if hasattr(scenario_input.parameters, key):
            setattr(scenario_input.parameters, key, value)


def apply_custom_downtimes(
    scenario_input,
    custom_downtimes: List[Dict[str, Any]] | None
):
    if not custom_downtimes:
        scenario_input.custom_downtimes = []
        return

    scenario_input.custom_downtimes = custom_downtimes

    for downtime in custom_downtimes:
        machine_id = downtime.get("MachineID")

        if not machine_id:
            continue

        machine = scenario_input.machines.get(machine_id)

        if not machine:
            continue

        if not hasattr(machine, "Downtimes"):
            machine.Downtimes = []

        machine.Downtimes.append({
            "StartTime": downtime.get("StartTime"),
            "EndTime": downtime.get("EndTime"),
            "Reason": downtime.get("Reason", "Downtime"),
        })


def apply_custom_overrides(
    scenario_input,
    custom_calendar_overrides: Dict[str, Any] | None = None,
    custom_machine_overrides: Dict[str, Any] | None = None,
    custom_objective_overrides: Dict[str, Any] | None = None,
):
    if custom_calendar_overrides:
        scenario_input.custom_calendar_overrides = custom_calendar_overrides

    if custom_machine_overrides:
        for machine_id, machine_changes in custom_machine_overrides.items():
            machine = scenario_input.machines.get(machine_id)

            if not machine:
                continue

            for attr, value in machine_changes.items():
                if hasattr(machine, attr):
                    setattr(machine, attr, value)

    if custom_objective_overrides:
        scenario_input.objective_overrides = {
            **getattr(scenario_input, "objective_overrides", {}),
            **custom_objective_overrides,
        }


def get_effective_parameters(scenario_input) -> dict:
    params = scenario_input.parameters

    return {
        "WidthSetupPerUnit": params.WidthSetupPerUnit,
        "LateOrderPenalty": params.LateOrderPenalty,
        "PopulationSize": params.PopulationSize,
        "Generations": params.Generations,
        "MutationRate": params.MutationRate,
        "EliteSize": params.EliteSize,
        "TournamentSize": params.TournamentSize,
        "TemperatureSetupPer10DegreeMinutes": params.TemperatureSetupPer10DegreeMinutes,
        "MaximumAllowedGapBetweenHeatingAndPressHours": params.MaximumAllowedGapBetweenHeatingAndPressHours,
        "MaxOverSoakMinutes": params.MaxOverSoakMinutes,
    }


def build_planned_tasks_from_schedule(
    scheduled_ops,
    scenario_id: str
) -> list[PlannedTask]:

    planned_tasks = []

    for op in scheduled_ops:
        planned_task = PlannedTask(
            PlannedTaskID=f"{scenario_id}_{op.OperationID}",
            ScenarioID=scenario_id,

            WorkOrderID=op.WorkOrderID,
            OperationID=op.OperationID,
            SequenceNumber=op.SequenceNumber,

            PlannedMachine=op.AssignedMachine,

            SetupStart=op.SetupStart,
            StartTime=op.StartTime,
            EndTime=op.EndTime,

            HeatingEndTime=getattr(op, "HeatingEndTime", None),
            ReleaseTime=getattr(op, "ReleaseTime", None),
            WaitingMinutes=getattr(op, "WaitingMinutes", 0),

            DurationHours=op.DurationHours,
            BatchEndTime=getattr(op, "BatchEndTime", None),

            ProductFamily=getattr(op, "ProductFamily", None),
            Temperature=getattr(op, "Temperature", None),
            Weight=getattr(op, "Weight", None),
            Length=getattr(op, "Length", None),

            SetupMinutes=op.SetupMinutes,
            BatchID=op.BatchID,

            IsManual=False,
            IsUnplanned=False,

            ViolationStatus="VIOLATION"
            if op.Late
            else "OK",

            ViolationReasons=[
                reason
                for reason in [
                    "LATE" if op.Late else None,
                ]
                if reason is not None
            ],

            Source="GA",
            CreatedDate=datetime.now(),
            UpdatedDate=datetime.now(),
        )

        planned_tasks.append(planned_task)

    return planned_tasks


def build_scenario_kpis(
    scenario_id: str,
    kpi_record: dict
) -> ScenarioKPI:

    return ScenarioKPI(
        ScenarioID=scenario_id,

        FeasibleSchedule=bool(kpi_record.get("FeasibleSchedule", False)),
        InfeasibleCount=int(kpi_record.get("InfeasibleCount", 0)),
        OverSoakViolations=int(kpi_record.get("OverSoakViolations", 0)),

        TotalOperations=int(kpi_record.get("TotalOperations", 0)),
        LateOperations=int(kpi_record.get("LateOperations", 0)),
        DeliveryPerformancePercent=float(kpi_record.get("DeliveryPerformancePercent", 0)),

        LatePenalty=float(kpi_record.get("LatePenalty", 0)),

        TotalSetupMinutes=float(kpi_record.get("TotalSetupMinutes", 0)),
        FamilySetupMinutes=float(kpi_record.get("FamilySetupMinutes", 0)),
        WidthSetupMinutes=float(kpi_record.get("WidthSetupMinutes", 0)),
        TemperatureSetupMinutes=float(kpi_record.get("TemperatureSetupMinutes", 0)),

        OvenUtilizationPercent=float(kpi_record.get("OvenUtilizationPercent", 0)),
        MachineUtilizationPercent=float(kpi_record.get("MachineUtilizationPercent", 0)),

        ProductionHours=float(kpi_record.get("ProductionHours", 0)),
        TotalScheduleHours=float(kpi_record.get("TotalScheduleHours", 0)),
        TotalCost=float(kpi_record.get("TotalCost", 0)),
    )


def build_default_ga_scenario(
    scheduled_ops,
    kpi_record: dict,
    scenario_id: str,
    scenario_name: str,
    base_scenario_id: str | None = None,
) -> Scenario:

    scenario = create_scenario(
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        created_by="system",
        base_scenario_id=base_scenario_id,
    )

    scenario.CalendarID = "DEFAULT"
    scenario.PlannerNotes = "Generated by PlanWise scheduler using selected scenario definition."
    scenario.Status = "Active"

    planned_tasks = build_planned_tasks_from_schedule(
        scheduled_ops=scheduled_ops,
        scenario_id=scenario.ScenarioID,
    )

    for planned_task in planned_tasks:
        add_planned_task(scenario, planned_task)

    scenario.KPIs = build_scenario_kpis(
        scenario_id=scenario.ScenarioID,
        kpi_record=kpi_record,
    )

    return scenario


def run_ga_scheduler(
    scenario_id: str = "BASE",
    excel_file: str | None = None,
    custom_parameter_overrides: Dict[str, Any] | None = None,
    custom_downtimes: List[Dict[str, Any]] | None = None,
    custom_calendar_overrides: Dict[str, Any] | None = None,
    custom_machine_overrides: Dict[str, Any] | None = None,
    custom_objective_overrides: Dict[str, Any] | None = None,
):
    if excel_file is None:
        excel_file = BASE_DIR / "backend" / "uploads" / "orders.xlsx"

        if not excel_file.exists():
            excel_file = BASE_DIR / "data" / "orders.xlsx"

    scheduling_input = load_scheduling_input(excel_file)

    create_default_scenarios(scheduling_input)

    if scenario_id not in scheduling_input.scenario_definitions:
        base_definition = scheduling_input.scenario_definitions.get("BASE")

        scheduling_input.scenario_definitions[scenario_id] = ScenarioDefinition(
            ScenarioID=scenario_id,
            ScenarioName=scenario_id,
            BaseScenarioID="BASE",
            Description="User-created scenario from frontend.",

            CalendarOverrides={},
            RuleOverrides={},
            ParameterOverrides=custom_parameter_overrides or {},
            MachineOverrides=custom_machine_overrides or {},
            ObjectiveOverrides=custom_objective_overrides or {},

            IsBaseScenario=False,
        )

        if base_definition:
            scheduling_input.scenario_definitions[scenario_id].CalendarOverrides = {
                **(base_definition.CalendarOverrides or {}),
                **(custom_calendar_overrides or {}),
            }

            scheduling_input.scenario_definitions[scenario_id].ParameterOverrides = {
                **(base_definition.ParameterOverrides or {}),
                **(custom_parameter_overrides or {}),
            }

            scheduling_input.scenario_definitions[scenario_id].MachineOverrides = {
                **(base_definition.MachineOverrides or {}),
                **(custom_machine_overrides or {}),
            }

            scheduling_input.scenario_definitions[scenario_id].ObjectiveOverrides = {
                **(base_definition.ObjectiveOverrides or {}),
                **(custom_objective_overrides or {}),
            }

    scenario_definition = scheduling_input.scenario_definitions[scenario_id]

    

    scenario_input = apply_scenario_definition(
        scheduling_input,
        scenario_id,
    )

    apply_custom_parameter_overrides(
        scenario_input,
        custom_parameter_overrides,
    )

    apply_custom_downtimes(
        scenario_input,
        custom_downtimes,
    )

    apply_custom_overrides(
        scenario_input,
        custom_calendar_overrides=custom_calendar_overrides,
        custom_machine_overrides=custom_machine_overrides,
        custom_objective_overrides=custom_objective_overrides,
    )

    effective_parameters = get_effective_parameters(scenario_input)

    best_individual, result, history = run_ga(scenario_input)

    schedule_df = build_schedule_dataframe(result["scheduled_ops"])
    kpi_df = build_kpi_dataframe(result)
    machine_kpi_df = build_machine_kpis(result["machines"])
    history_df = pd.DataFrame(history)

    kpi_record = kpi_df.to_dict(orient="records")[0]

    scenario = build_default_ga_scenario(
        scheduled_ops=result["scheduled_ops"],
        kpi_record=kpi_record,
        scenario_id=scenario_definition.ScenarioID,
        scenario_name=scenario_definition.ScenarioName,
        base_scenario_id=scenario_definition.BaseScenarioID,
    )

    from collections import defaultdict

    batch_check = defaultdict(list)

    for task in scenario.PlannedTasks:
        if not task.BatchID:
            continue

        batch_check[task.BatchID].append({
            "WO": task.WorkOrderID,
            "Machine": task.PlannedMachine,
            "Start": task.StartTime,
            "End": task.EndTime,
        })

    print("\n========== BATCH VALIDATION ==========\n")

    for batch_id, rows in batch_check.items():
        starts = {str(r["Start"]) for r in rows}
        machines = {str(r["Machine"]) for r in rows}

        if len(starts) > 1 or len(machines) > 1:
            print(f"\nINVALID BATCH: {batch_id}")

            for r in rows:
                print(
                    r["WO"],
                    r["Machine"],
                    r["Start"],
                    r["End"]
                )



    scenario_input.scenarios[scenario.ScenarioID] = scenario
    scenario_input.active_scenario_id = scenario.ScenarioID

    gantt_rows = schedule_df.rename(
        columns={
            "ProductionStart": "StartTime",
            "ProductionEnd": "EndTime",
        }
    )

    gantt_rows = gantt_rows[
        [
            "OperationID",
            "WorkOrderID",
            "AssignedMachine",
            "SetupStart",
            "StartTime",
            "EndTime",
            "ProductFamily",
            "Temperature",
            "SequenceNumber",
        ]
    ].copy()

    excel_path = OUTPUT_DIR / f"{scenario_id.lower()}_ga_aps_solution.xlsx"
    gantt_path = OUTPUT_DIR / f"{scenario_id.lower()}_ga_aps_gantt.png"

    planned_tasks_df = pd.DataFrame(
        [serialize_planned_task(task) for task in scenario.PlannedTasks]
    )

    scenario_kpi_df = pd.DataFrame([asdict(scenario.KPIs)])

    scenario_df = pd.DataFrame([
        {
            **serialize_scenario(scenario),
            "ScenarioDescription": scenario_definition.Description,
            "RuleOverrides": str(scenario_definition.RuleOverrides),
            "ParameterOverrides": str(scenario_definition.ParameterOverrides),
            "CustomParameterOverrides": str(custom_parameter_overrides or {}),
            "EffectiveParameters": str(effective_parameters),
            "Downtimes": str(custom_downtimes or []),
            "CalendarOverrides": str(custom_calendar_overrides or scenario_definition.CalendarOverrides),
            "MachineOverrides": str(custom_machine_overrides or scenario_definition.MachineOverrides),
            "ObjectiveOverrides": str(custom_objective_overrides or scenario_definition.ObjectiveOverrides),
        }
    ])

    with pd.ExcelWriter(excel_path) as writer:
        kpi_df.to_excel(writer, sheet_name="KPIs", index=False)
        machine_kpi_df.to_excel(writer, sheet_name="Machine KPIs", index=False)
        schedule_df.to_excel(writer, sheet_name="Schedule", index=False)
        history_df.to_excel(writer, sheet_name="GA History", index=False)

        scenario_df.to_excel(writer, sheet_name="Scenario", index=False)
        planned_tasks_df.to_excel(writer, sheet_name="Planned Tasks", index=False)
        scenario_kpi_df.to_excel(writer, sheet_name="Scenario KPIs", index=False)

    create_gantt_chart(
        schedule_df,
        result["machines"],
        gantt_path,
    )

    response_scenario = {
        **serialize_scenario(scenario),
        "ScenarioDescription": scenario_definition.Description,
        "RuleOverrides": scenario_definition.RuleOverrides,
        "ParameterOverrides": scenario_definition.ParameterOverrides,
        "CustomParameterOverrides": custom_parameter_overrides or {},
        "EffectiveParameters": effective_parameters,
        "Downtimes": custom_downtimes or [],
        "CalendarOverrides": custom_calendar_overrides or scenario_definition.CalendarOverrides,
        "MachineOverrides": custom_machine_overrides or scenario_definition.MachineOverrides,
        "ObjectiveOverrides": custom_objective_overrides or scenario_definition.ObjectiveOverrides,
    }

    response_planned_tasks = [
        serialize_planned_task(task)
        for task in scenario.PlannedTasks
    ]

    save_scenario_result_to_excel(
        scenario=response_scenario,
        scenario_kpis=asdict(scenario.KPIs),
        planned_tasks=response_planned_tasks,
        schedule=schedule_df.astype(str).to_dict(orient="records"),
        machine_kpis=machine_kpi_df.to_dict(orient="records"),
    )

    

    return {
        "message": "Optimization completed successfully",

        "activeScenarioId": scenario.ScenarioID,

        "scenario": response_scenario,


        "effectiveParameters": effective_parameters,
        "kpis": kpi_record,
        "scenarioKpis": asdict(scenario.KPIs),

        "plannedTasks": response_planned_tasks,

        "schedule": schedule_df.astype(str).to_dict(orient="records"),
        "machineKpis": machine_kpi_df.to_dict(orient="records"),
        "workOrderSequence": best_individual["work_order_order"],
        "gantt": gantt_rows.astype(str).to_dict(orient="records"),

        "files": {
            "excel": str(excel_path),
            "gantt": str(gantt_path),
        },
    }