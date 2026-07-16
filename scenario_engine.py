# scenario_engine.py

from copy import deepcopy
from datetime import datetime
from uuid import uuid4
from typing import Optional, Any

from models import (
    SchedulingInput,
    ScenarioDefinition,
    Scenario,
    PlannedTask,
    ManualChange,
)


def create_default_scenarios(
    scheduling_input: SchedulingInput
):
    base = ScenarioDefinition(
        ScenarioID="BASE",
        ScenarioName="Base Scenario",
        Description="Original imported planning data.",
        IsBaseScenario=True,
        ParameterOverrides={
            "LateOrderPenalty": 1000,
            "MaxOverSoakMinutes": 240,
            "PopulationSize": 100,
            "Generations": 20,
            "MutationRate": 0.30,
        },
    )

    aggressive = ScenarioDefinition(
        ScenarioID="AGGRESSIVE",
        ScenarioName="Aggressive Delivery",
        BaseScenarioID="BASE",
        Description="Prioritize delivery performance.",
        ParameterOverrides={
            "LateOrderPenalty": 10000,
            "MaxOverSoakMinutes": 180,
            "PopulationSize": 250,
            "Generations": 60,
            "MutationRate": 0.40,
        },
        ObjectiveOverrides={
            "PrioritizeDelivery": True,
        },
    )

    energy = ScenarioDefinition(
        ScenarioID="ENERGY",
        ScenarioName="Energy Saving",
        BaseScenarioID="BASE",
        Description="Reduce oven energy usage and temperature changes.",
        ParameterOverrides={
            "LateOrderPenalty": 500,
            "TemperatureSetupPer10DegreeMinutes": 45,
            "PopulationSize": 200,
            "Generations": 50,
            "MutationRate": 0.35,
        },
        ObjectiveOverrides={
            "PrioritizeOvenUtilization": True,
            "PrioritizeTemperatureStability": True,
        },
    )

    low_setup = ScenarioDefinition(
        ScenarioID="LOW_SETUP",
        ScenarioName="Low Setup Plan",
        BaseScenarioID="BASE",
        Description="Prioritize setup reduction.",
        ParameterOverrides={
            "LateOrderPenalty": 1000,
            "WidthSetupPerUnit": 25,
            "TemperatureSetupPer10DegreeMinutes": 35,
            "PopulationSize": 250,
            "Generations": 70,
            "MutationRate": 0.35,
        },
        ObjectiveOverrides={
            "PrioritizeSetupReduction": True,
        },
    )

    maintenance = ScenarioDefinition(
        ScenarioID="MAINTENANCE",
        ScenarioName="Maintenance Shutdown",
        BaseScenarioID="BASE",
        Description="Oven1 maintenance shutdown.",
        CalendarOverrides={
            "Oven1": {
                "UnavailableDates": [
                    "2026-05-21"
                ]
            }
        },
        ParameterOverrides={
            "LateOrderPenalty": 2000,
            "PopulationSize": 200,
            "Generations": 50,
            "MutationRate": 0.40,
        },
    )

    scheduling_input.scenario_definitions = {
        base.ScenarioID: base,
        aggressive.ScenarioID: aggressive,
        energy.ScenarioID: energy,
        low_setup.ScenarioID: low_setup,
        maintenance.ScenarioID: maintenance,
    }


def apply_scenario_definition(
    base_input: SchedulingInput,
    scenario_id: str
) -> SchedulingInput:

    scenario_definition = base_input.scenario_definitions.get(
        scenario_id
    )

    if not scenario_definition:
        raise Exception(
            f"Scenario definition not found: {scenario_id}"
        )

    scenario_input = deepcopy(base_input)
    scenario_input.active_scenario_id = scenario_id

    all_parameter_overrides = {}

    all_parameter_overrides.update(
        scenario_definition.RuleOverrides
    )

    all_parameter_overrides.update(
        scenario_definition.ParameterOverrides
    )

    for parameter_name, parameter_value in all_parameter_overrides.items():
        if hasattr(scenario_input.parameters, parameter_name):
            setattr(
                scenario_input.parameters,
                parameter_name,
                parameter_value
            )

    for machine_id, machine_changes in scenario_definition.MachineOverrides.items():
        machine = scenario_input.machines.get(machine_id)

        if not machine:
            continue

        for attr, value in machine_changes.items():
            if hasattr(machine, attr):
                setattr(machine, attr, value)

    scenario_input.objective_overrides = deepcopy(
        scenario_definition.ObjectiveOverrides
    )

    return scenario_input


def create_scenario(
    scenario_name: str,
    created_by: str = "system",
    base_scenario_id: Optional[str] = None,
    scenario_id: Optional[str] = None,
) -> Scenario:

    return Scenario(
        ScenarioID=scenario_id or f"SCN_{uuid4().hex[:8]}",
        ScenarioName=scenario_name,
        CreatedBy=created_by,
        CreatedDate=datetime.now(),
        BaseScenarioID=base_scenario_id,
        IsManualScenario=False,
        Status="Active",
    )


def add_planned_task(
    scenario: Scenario,
    planned_task: PlannedTask,
):
    scenario.PlannedTasks.append(planned_task)


def record_manual_change(
    scenario: Scenario,
    planned_task: PlannedTask,
    change_type: str,
    old_value: Optional[Any],
    new_value: Optional[Any],
    changed_by: str = "planner",
    note: Optional[str] = None,
):

    change = ManualChange(
        ManualChangeID=f"MC_{uuid4().hex[:8]}",
        ScenarioID=scenario.ScenarioID,
        PlannedTaskID=planned_task.PlannedTaskID,
        ChangeType=change_type,
        OldValue=old_value,
        NewValue=new_value,
        ChangedBy=changed_by,
        ChangedDate=datetime.now(),
        Note=note,
    )

    scenario.ManualChanges.append(change)
    scenario.IsManualScenario = True

    return change


def get_planned_task(
    scenario: Scenario,
    planned_task_id: str,
) -> Optional[PlannedTask]:

    for task in scenario.PlannedTasks:
        if task.PlannedTaskID == planned_task_id:
            return task

    return None


def unplan_task(
    scenario: Scenario,
    planned_task_id: str,
):

    task = get_planned_task(
        scenario,
        planned_task_id,
    )

    if not task:
        return None

    old_value = {
        "PlannedMachine": task.PlannedMachine,
        "StartTime": str(task.StartTime),
        "EndTime": str(task.EndTime),
    }

    task.IsUnplanned = True

    record_manual_change(
        scenario=scenario,
        planned_task=task,
        change_type="UNPLAN",
        old_value=old_value,
        new_value={"IsUnplanned": True},
    )

    return task