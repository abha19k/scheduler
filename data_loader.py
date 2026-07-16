import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional

from models import Operation, Machine, Parameters, SchedulingInput


def clean_str(value, default: str = "") -> str:
    if pd.isna(value):
        return default
    return str(value).strip()


def optional_float(value) -> Optional[float]:
    if pd.isna(value) or value == "" or str(value).strip() == "-":
        return None
    return float(value)


def parse_datetime(value):
    if pd.isna(value) or value == "":
        return None
    return pd.to_datetime(value).to_pydatetime()


def duration_to_hours(value) -> float:
    if pd.isna(value):
        return 0.0

    if isinstance(value, pd.Timedelta):
        return value.total_seconds() / 3600

    if hasattr(value, "hour"):
        return value.hour + value.minute / 60 + value.second / 3600

    if isinstance(value, str):
        try:
            td = pd.to_timedelta(value)
            return td.total_seconds() / 3600
        except Exception:
            return float(value)

    return float(value)


def split_allowed_machines(value) -> list[str]:
    if pd.isna(value):
        return []

    return [
        machine.strip()
        for machine in str(value).split(",")
        if machine.strip()
    ]


def get_first_existing(row, possible_columns, default=None):
    for col in possible_columns:
        if col in row.index:
            return row.get(col)
    return default


def get_param(param_dict: Dict[str, Any], name: str, default):
    value = param_dict.get(name, default)

    if pd.isna(value):
        return default

    return value


def load_parameters(parameters_df: pd.DataFrame) -> Parameters:
    parameters_df["Parameter"] = parameters_df["Parameter"].astype(str).str.strip()

    param_dict = {}
    objectives = []

    for _, row in parameters_df.iterrows():
        parameter = clean_str(row.get("Parameter"))
        value = row.get("Value")

        if parameter == "Objective":
            objectives.append(clean_str(value))
        else:
            param_dict[parameter] = value

    planning_start = get_param(param_dict, "PlanningStart", None)

    return Parameters(
        WidthSetupPerUnit=int(get_param(param_dict, "WidthSetupPerUnit", 10)),
        LateOrderPenalty=int(get_param(param_dict, "LateOrderPenalty", 1000)),

        PopulationSize=int(get_param(param_dict, "PopulationSize", 200)),
        Generations=int(get_param(param_dict, "Generations", 20)),
        MutationRate=float(get_param(param_dict, "MutationRate", 0.30)),
        EliteSize=int(get_param(param_dict, "EliteSize", 10)),
        TournamentSize=int(get_param(param_dict, "TournamentSize", 3)),

        TemperatureSetupPer10DegreeMinutes=int(
            get_param(param_dict, "TemperatureSetupPer10DegreeMinutes", 15)
        ),

        MaximumAllowedGapBetweenHeatingAndPressHours=float(
            get_param(param_dict, "MaximumAllowedGapBetweenHeatingAndPressHours", 4)
        ),

        MaxOverSoakMinutes=int(
            get_param(param_dict, "MaxOverSoakMinutes", 240)
        ),

        Objectives=objectives,
        PlanningStart=parse_datetime(planning_start),
    )


def load_machines(machines_df: pd.DataFrame) -> Dict[str, Machine]:
    machines = {}

    for _, row in machines_df.iterrows():
        machine_id = clean_str(row.get("MachineID"))

        if not machine_id:
            continue

        machine_type = clean_str(
            get_first_existing(row, ["MachineType", "Type"], "Regular"),
            "Regular"
        )

        machine = Machine(
            MachineID=machine_id,
            MachineType=machine_type,

            ParallelCapacity=int(
                get_first_existing(row, ["ParallelCapacity"], 1)
            )
            if not pd.isna(get_first_existing(row, ["ParallelCapacity"], 1))
            else 1,

            Status=clean_str(row.get("Status"), "Active"),

            StartTime=parse_datetime(row.get("StartTime")),
            EndTime=parse_datetime(row.get("EndTime")),

            MaxWeight=optional_float(
                get_first_existing(row, ["MaxWeight", "MaxAllowedWeight (Ton)"])
            ),

            MaxLength=optional_float(
                get_first_existing(row, ["MaxLength", "Max Length (meter)"])
            ),

            MaxTemperature=optional_float(
                get_first_existing(row, ["MaxTemperature", "Max Temperature (celcius)"])
            ),
        )

        machines[machine_id] = machine

    return machines


def load_family_setup_matrix(setup_df: pd.DataFrame) -> Dict[tuple, float]:
    setup_matrix = {}

    for _, row in setup_df.iterrows():
        from_family = clean_str(row.get("FromProductFamily"))
        to_family = clean_str(row.get("ToProductFamily"))

        if not from_family or not to_family:
            continue

        setup_minutes = float(row.get("SetupMinutes", 0))
        setup_matrix[(from_family, to_family)] = setup_minutes

    return setup_matrix


def load_operations(orders_df: pd.DataFrame) -> list[Operation]:
    operations = []

    for _, row in orders_df.iterrows():
        work_order_id = clean_str(row.get("WorkOrderID"))
        sequence_number = int(row.get("SequenceNumber", 1))

        operation_id = clean_str(
            row.get("OperationID"),
            f"{work_order_id}_OP{sequence_number}"
        )

        due_date = parse_datetime(row.get("DueDate"))

        if due_date is None:
            raise ValueError(f"DueDate missing for WorkOrderID {work_order_id}")

        allowed_machine_value = get_first_existing(
            row,
            ["AllowedMachines", "AllowedMachine", "MachineID"],
            ""
        )

        priority_value = row.get("Priority", 1)
        priority = 1 if pd.isna(priority_value) else int(priority_value)

        operation = Operation(
            WorkOrderID=work_order_id,
            OperationID=operation_id,
            SequenceNumber=sequence_number,
            OperationType=clean_str(row.get("OperationType"), "Production"),

            AllowedMachines=split_allowed_machines(allowed_machine_value),

            DurationHours=duration_to_hours(row.get("DurationHours")),
            DueDate=due_date,
            EarliestStart=parse_datetime(row.get("EarliestStart")),

            Width=optional_float(row.get("Width")),
            Color=clean_str(row.get("Color")),
            Tool=clean_str(row.get("Tool")),
            ProductFamily=clean_str(row.get("ProductFamily")),

            Weight=optional_float(
                get_first_existing(row, ["Weight", "Weight (Ton)"])
            ),

            Length=optional_float(
                get_first_existing(row, ["Length", "Length (m)"])
            ),

            Temperature=optional_float(
                get_first_existing(row, ["Temperature", "NominalTemperature"])
            ),

            Priority=priority,
        )

        operations.append(operation)

    operations.sort(
        key=lambda op: (
            op.WorkOrderID,
            op.SequenceNumber
        )
    )

    return operations


def validate_input(
    operations: list[Operation],
    machines: Dict[str, Machine]
) -> None:

    if not operations:
        raise ValueError("No operations found in Orders sheet.")

    if not machines:
        raise ValueError("No machines found in Machines sheet.")

    machine_ids = set(machines.keys())

    for op in operations:
        if not op.AllowedMachines:
            raise ValueError(
                f"Operation {op.OperationID} has no allowed machines."
            )

        invalid_machines = [
            m for m in op.AllowedMachines
            if m not in machine_ids
        ]

        if invalid_machines:
            raise ValueError(
                f"Operation {op.OperationID} has invalid machines: {invalid_machines}"
            )

        if op.DurationHours <= 0:
            raise ValueError(
                f"Operation {op.OperationID} has invalid DurationHours."
            )


def load_scheduling_input(excel_file: str | Path) -> SchedulingInput:
    excel_file = Path(excel_file)

    if not excel_file.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_file}")

    orders_df = pd.read_excel(excel_file, sheet_name="Orders")
    machines_df = pd.read_excel(excel_file, sheet_name="Machines")
    setup_df = pd.read_excel(excel_file, sheet_name="SetupMatrix")
    parameters_df = pd.read_excel(excel_file, sheet_name="Parameters")

    parameters = load_parameters(parameters_df)
    machines = load_machines(machines_df)
    family_setup_matrix = load_family_setup_matrix(setup_df)
    operations = load_operations(orders_df)

    validate_input(operations, machines)

    if parameters.PlanningStart is None:
        machine_starts = [
            m.StartTime for m in machines.values()
            if m.StartTime is not None
        ]

        if machine_starts:
            parameters.PlanningStart = min(machine_starts)

    return SchedulingInput(
        operations=operations,
        machines=machines,
        family_setup_matrix=family_setup_matrix,
        parameters=parameters,
    )


if __name__ == "__main__":
    data = load_scheduling_input("data/orders.xlsx")

    print("\nLoaded Scheduling Input")
    print("-----------------------")
    print(f"Operations: {len(data.operations)}")
    print(f"Machines: {len(data.machines)}")
    print(f"Family setup rules: {len(data.family_setup_matrix)}")
    print(f"Planning start: {data.parameters.PlanningStart}")
    print(f"Max over-soak minutes: {data.parameters.MaxOverSoakMinutes}")
    print(f"Objectives: {data.parameters.Objectives}")

    print("\nFirst 5 operations:")
    for op in data.operations[:5]:
        print(op)