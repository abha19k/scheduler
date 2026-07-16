# assignment_engine.py

from datetime import timedelta

from constraints import (
    machine_can_process,
)


# =========================================================
# MACHINE LOAD
# =========================================================

def machine_current_load(machine):

    if not machine.Timeline:
        return 0

    total = 0

    for item in machine.Timeline:

        total += (
            item["EndTime"] - item["StartTime"]
        ).total_seconds() / 60

    return total


# =========================================================
# LAST MACHINE OPERATION
# =========================================================

def get_last_machine_operation(machine):

    if not machine.Timeline:
        return None

    latest = max(
        machine.Timeline,
        key=lambda x: x["EndTime"]
    )

    return latest


# =========================================================
# MACHINE SCORE
# =========================================================

def score_machine(
    operation,
    machine,
    scheduled_operations,
    scheduling_input,
):

    score = 0

    # =====================================================
    # HARD FEASIBILITY
    # =====================================================

    if not machine_can_process(operation, machine):
        return 999999999

    # =====================================================
    # PREVIOUS OPERATION IN SAME WORK ORDER
    # =====================================================

    previous_op = None

    for op in scheduled_operations:
        if (
            op.WorkOrderID == operation.WorkOrderID
            and op.SequenceNumber == operation.SequenceNumber - 1
        ):
            previous_op = op
            break

    # =====================================================
    # SAME MACHINE BONUS
    # =====================================================

    if previous_op is not None:

        if previous_op.AssignedMachine == machine.MachineID:
            score -= 500

    # =====================================================
    # MACHINE HISTORY
    # =====================================================

    last_machine_item = get_last_machine_operation(machine)

    if last_machine_item is not None:

        last_op = last_machine_item["Operation"]

        # -------------------------------------------------
        # SAME PRODUCT FAMILY
        # -------------------------------------------------

        if (
            last_op.ProductFamily
            and operation.ProductFamily
            and last_op.ProductFamily == operation.ProductFamily
        ):
            score -= 300

        # -------------------------------------------------
        # SAME TEMPERATURE
        # -------------------------------------------------

        if (
            last_op.Temperature is not None
            and operation.Temperature is not None
        ):

            temp_diff = abs(
                last_op.Temperature
                - operation.Temperature
            )

            if temp_diff == 0:
                score -= 250

            else:
                score += temp_diff * 2

        # -------------------------------------------------
        # SETUP PENALTY
        # -------------------------------------------------

        family_setup = scheduling_input.family_setup_matrix.get(
            (
                last_op.ProductFamily,
                operation.ProductFamily
            ),
            0
        )

        score += family_setup

    # =====================================================
    # MACHINE LOAD BALANCING
    # =====================================================

    load_minutes = machine_current_load(machine)

    score += load_minutes * 0.02

    # =====================================================
    # OVEN BATCH BONUS
    # =====================================================

    if machine.MachineType.lower() == "batch":

        active_batches = 0

        for item in machine.Timeline:

            existing_op = item["Operation"]

            if (
                existing_op.Temperature == operation.Temperature
                and existing_op.ProductFamily == operation.ProductFamily
            ):
                active_batches += 1

        score -= active_batches * 150

    return score


# =========================================================
# CHOOSE BEST MACHINE
# =========================================================

def choose_best_machine(
    operation,
    machines,
    scheduled_operations,
    scheduling_input,
):

    feasible = []

    for machine in machines.values():

        if machine_can_process(operation, machine):

            score = score_machine(
                operation,
                machine,
                scheduled_operations,
                scheduling_input,
            )

            feasible.append(
                (score, machine)
            )

    if not feasible:
        return None

    feasible.sort(
        key=lambda x: x[0]
    )

    return feasible[0][1]


# =========================================================
# CREATE SMART ASSIGNMENT
# =========================================================


def create_smart_assignment(
    operations,
    machines,
    scheduling_input,
):

    assignment = {}
    scheduled_operations = []
    batch_preferences = {}

    sorted_ops = sorted(
        operations,
        key=lambda x: (
            x.DueDate,
            x.WorkOrderID,
            x.SequenceNumber,
        )
    )

    for op in sorted_ops:

        operation_type = (
            op.OperationType or ""
        ).lower()

        is_heating = (
            "heat" in operation_type
            or "oven" in operation_type
        )

        batch_key = (
            op.ProductFamily,
            op.Temperature
        )

        if (
            is_heating
            and batch_key in batch_preferences
        ):
            preferred_machine_id = batch_preferences[batch_key]

            if preferred_machine_id in machines:
                assignment[op.OperationID] = preferred_machine_id
                op.AssignedMachine = preferred_machine_id
                scheduled_operations.append(op)
                continue

        best_machine = choose_best_machine(
            operation=op,
            machines=machines,
            scheduled_operations=scheduled_operations,
            scheduling_input=scheduling_input,
        )

        if best_machine is None:
            raise ValueError(
                f"No feasible machine for {op.OperationID}"
            )

        assignment[op.OperationID] = best_machine.MachineID
        op.AssignedMachine = best_machine.MachineID

        if is_heating:
            batch_preferences[batch_key] = best_machine.MachineID

        scheduled_operations.append(op)

    return assignment
