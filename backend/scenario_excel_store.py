from pathlib import Path
from datetime import datetime
import json
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "backend" / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

SCENARIO_STORE_PATH = STORAGE_DIR / "planwise_scenario_store.xlsx"


def _read_sheet(sheet_name: str) -> pd.DataFrame:
    if not SCENARIO_STORE_PATH.exists():
        return pd.DataFrame()

    try:
        return pd.read_excel(SCENARIO_STORE_PATH, sheet_name=sheet_name)
    except Exception:
        return pd.DataFrame()


def _write_store(sheets: dict[str, pd.DataFrame]) -> None:
    with pd.ExcelWriter(SCENARIO_STORE_PATH, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)


def save_scenario_result_to_excel(
    scenario: dict,
    scenario_kpis: dict,
    planned_tasks: list[dict],
    schedule: list[dict],
    machine_kpis: list[dict],
) -> None:
    definitions_df = _read_sheet("ScenarioDefinitions")
    scenarios_df = _read_sheet("Scenarios")
    kpis_df = _read_sheet("ScenarioKPIs")
    planned_tasks_df = _read_sheet("PlannedTasks")
    schedule_df = _read_sheet("Schedule")
    machine_kpis_df = _read_sheet("MachineKPIs")

    scenario_id = scenario["ScenarioID"]

    if not scenarios_df.empty and "ScenarioID" in scenarios_df.columns:
        scenarios_df = scenarios_df[scenarios_df["ScenarioID"] != scenario_id]

    if not kpis_df.empty and "ScenarioID" in kpis_df.columns:
        kpis_df = kpis_df[kpis_df["ScenarioID"] != scenario_id]

    if not planned_tasks_df.empty and "ScenarioID" in planned_tasks_df.columns:
        planned_tasks_df = planned_tasks_df[
            planned_tasks_df["ScenarioID"] != scenario_id
        ]

    if not schedule_df.empty and "ScenarioID" in schedule_df.columns:
        schedule_df = schedule_df[schedule_df["ScenarioID"] != scenario_id]

    if not machine_kpis_df.empty and "ScenarioID" in machine_kpis_df.columns:
        machine_kpis_df = machine_kpis_df[
            machine_kpis_df["ScenarioID"] != scenario_id
        ]

    scenario_row = {
        **scenario,
        "SavedAt": datetime.now().isoformat(timespec="seconds"),
    }

    scenarios_df = pd.concat(
        [scenarios_df, pd.DataFrame([scenario_row])],
        ignore_index=True
    )

    kpis_df = pd.concat(
        [kpis_df, pd.DataFrame([{**scenario_kpis, "ScenarioID": scenario_id}])],
        ignore_index=True
    )

    planned_tasks_df = pd.concat(
        [planned_tasks_df, pd.DataFrame(planned_tasks)],
        ignore_index=True
    )

    schedule_with_scenario = [
        {**row, "ScenarioID": scenario_id}
        for row in schedule
    ]

    schedule_df = pd.concat(
        [schedule_df, pd.DataFrame(schedule_with_scenario)],
        ignore_index=True
    )

    machine_kpis_with_scenario = [
        {**row, "ScenarioID": scenario_id}
        for row in machine_kpis
    ]

    machine_kpis_df = pd.concat(
        [machine_kpis_df, pd.DataFrame(machine_kpis_with_scenario)],
        ignore_index=True
    )

    _write_store({
        "ScenarioDefinitions": definitions_df,
        "Scenarios": scenarios_df,
        "ScenarioKPIs": kpis_df,
        "PlannedTasks": planned_tasks_df,
        "Schedule": schedule_df,
        "MachineKPIs": machine_kpis_df,
    })


def load_saved_scenarios_from_excel() -> list[dict]:
    scenarios_df = _read_sheet("Scenarios")
    kpis_df = _read_sheet("ScenarioKPIs")
    planned_tasks_df = _read_sheet("PlannedTasks")

    if scenarios_df.empty:
        return []

    results = []

    for _, scenario_row in scenarios_df.fillna("").iterrows():
        scenario = scenario_row.to_dict()
        scenario_id = scenario.get("ScenarioID")

        kpi_rows = (
            kpis_df[kpis_df["ScenarioID"] == scenario_id]
            .fillna("")
            .to_dict(orient="records")
            if not kpis_df.empty and "ScenarioID" in kpis_df.columns
            else []
        )

        task_rows = (
            planned_tasks_df[planned_tasks_df["ScenarioID"] == scenario_id]
            .fillna("")
            .to_dict(orient="records")
            if not planned_tasks_df.empty and "ScenarioID" in planned_tasks_df.columns
            else []
        )

        scenario["KPIs"] = kpi_rows[0] if kpi_rows else {}
        scenario["PlannedTasks"] = task_rows
        scenario["ManualChanges"] = []

        results.append(scenario)

    return results


def save_scenario_definition_to_excel(definition: dict) -> None:
    definitions_df = _read_sheet("ScenarioDefinitions")

    scenario_id = definition["ScenarioID"]

    if not definitions_df.empty and "ScenarioID" in definitions_df.columns:
        definitions_df = definitions_df[
            definitions_df["ScenarioID"] != scenario_id
        ]

    row = {
        "ScenarioID": definition.get("ScenarioID"),
        "ScenarioName": definition.get("ScenarioName"),
        "BaseScenarioID": definition.get("BaseScenarioID"),
        "Description": definition.get("Description", ""),
        "ParameterOverrides": json.dumps(definition.get("ParameterOverrides", {})),
        "CalendarOverrides": json.dumps(definition.get("CalendarOverrides", {})),
        "MachineOverrides": json.dumps(definition.get("MachineOverrides", {})),
        "ObjectiveOverrides": json.dumps(definition.get("ObjectiveOverrides", {})),
        "Downtimes": json.dumps(definition.get("Downtimes", [])),
        "SavedAt": datetime.now().isoformat(timespec="seconds"),
    }

    definitions_df = pd.concat(
        [definitions_df, pd.DataFrame([row])],
        ignore_index=True
    )

    _write_store({
        "ScenarioDefinitions": definitions_df,
        "Scenarios": _read_sheet("Scenarios"),
        "ScenarioKPIs": _read_sheet("ScenarioKPIs"),
        "PlannedTasks": _read_sheet("PlannedTasks"),
        "Schedule": _read_sheet("Schedule"),
        "MachineKPIs": _read_sheet("MachineKPIs"),
    })


def load_scenario_definitions_from_excel() -> list[dict]:
    definitions_df = _read_sheet("ScenarioDefinitions")

    if definitions_df.empty:
        return []

    definitions = []

    for _, row in definitions_df.fillna("").iterrows():
        definitions.append({
            "ScenarioID": row.get("ScenarioID"),
            "ScenarioName": row.get("ScenarioName"),
            "BaseScenarioID": row.get("BaseScenarioID") or None,
            "Description": row.get("Description", ""),
            "ParameterOverrides": json.loads(row.get("ParameterOverrides") or "{}"),
            "CalendarOverrides": json.loads(row.get("CalendarOverrides") or "{}"),
            "MachineOverrides": json.loads(row.get("MachineOverrides") or "{}"),
            "ObjectiveOverrides": json.loads(row.get("ObjectiveOverrides") or "{}"),
            "Downtimes": json.loads(row.get("Downtimes") or "[]"),
        })

    return definitions



def delete_scenario_from_excel(
    scenario_id: str
) -> None:

    scenarios_df = _read_sheet("Scenarios")
    kpis_df = _read_sheet("ScenarioKPIs")
    planned_tasks_df = _read_sheet("PlannedTasks")
    schedule_df = _read_sheet("Schedule")
    machine_kpis_df = _read_sheet("MachineKPIs")
    definitions_df = _read_sheet("ScenarioDefinitions")

    if not scenarios_df.empty and "ScenarioID" in scenarios_df.columns:
        scenarios_df = scenarios_df[
            scenarios_df["ScenarioID"] != scenario_id
        ]

    if not kpis_df.empty and "ScenarioID" in kpis_df.columns:
        kpis_df = kpis_df[
            kpis_df["ScenarioID"] != scenario_id
        ]

    if not planned_tasks_df.empty and "ScenarioID" in planned_tasks_df.columns:
        planned_tasks_df = planned_tasks_df[
            planned_tasks_df["ScenarioID"] != scenario_id
        ]

    if not schedule_df.empty and "ScenarioID" in schedule_df.columns:
        schedule_df = schedule_df[
            schedule_df["ScenarioID"] != scenario_id
        ]

    if not machine_kpis_df.empty and "ScenarioID" in machine_kpis_df.columns:
        machine_kpis_df = machine_kpis_df[
            machine_kpis_df["ScenarioID"] != scenario_id
        ]

    if not definitions_df.empty and "ScenarioID" in definitions_df.columns:
        definitions_df = definitions_df[
            definitions_df["ScenarioID"] != scenario_id
        ]

    _write_store({
        "Scenarios": scenarios_df,
        "ScenarioKPIs": kpis_df,
        "PlannedTasks": planned_tasks_df,
        "Schedule": schedule_df,
        "MachineKPIs": machine_kpis_df,
        "ScenarioDefinitions": definitions_df
    })