# machine_engine.py

from datetime import timedelta, datetime
from copy import deepcopy
from uuid import uuid4

from constraints import machine_can_process
from calendar_utils import adjust_to_calendar




# =========================================================
# DATETIME HELPERS
# =========================================================

def parse_datetime(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    value = str(value).replace("T", " ")

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def block_overlaps(start_a, end_a, start_b, end_b):
    return start_a < end_b and end_a > start_b


def adjust_to_machine_downtime(machine, proposed_start, total_block_hours):
    """
    Moves a task after downtime if its full setup+production block overlaps downtime.

    Downtime format expected on machine:
    machine.Downtimes = [
        {
            "StartTime": "2026-05-21T08:00",
            "EndTime": "2026-05-21T18:00",
            "Reason": "Maintenance"
        }
    ]
    """

    downtimes = getattr(machine, "Downtimes", [])

    if not downtimes:
        return proposed_start

    current_start = proposed_start
    duration = timedelta(hours=total_block_hours)

    changed = True

    while changed:
        changed = False
        current_end = current_start + duration

        for downtime in downtimes:
            downtime_start = parse_datetime(downtime.get("StartTime"))
            downtime_end = parse_datetime(downtime.get("EndTime"))

            if downtime_start is None or downtime_end is None:
                continue

            if downtime_end <= downtime_start:
                continue

            if block_overlaps(
                current_start,
                current_end,
                downtime_start,
                downtime_end
            ):
                current_start = downtime_end
                changed = True
                break

    return current_start


def adjust_to_calendar_and_downtime(
    machine,
    calendar_details,
    proposed_start,
    total_block_hours
):
    """
    First aligns to calendar, then avoids machine downtime.
    Repeats because moving after downtime may again violate calendar.
    """

    current_start = proposed_start

    for _ in range(20):
        calendar_start = adjust_to_calendar(
            machine,
            calendar_details,
            current_start,
            total_block_hours
        )

        downtime_start = adjust_to_machine_downtime(
            machine,
            calendar_start,
            total_block_hours
        )

        if downtime_start == current_start or downtime_start == calendar_start:
            return downtime_start

        current_start = downtime_start

    return current_start


# =========================================================
# SETUP CALCULATIONS
# =========================================================

def family_setup_minutes(prev_op, curr_op, setup_matrix):
    if prev_op is None:
        return 0

    if not prev_op.ProductFamily or not curr_op.ProductFamily:
        return 0

    if prev_op.ProductFamily == curr_op.ProductFamily:
        return 0

    return setup_matrix.get(
        (prev_op.ProductFamily, curr_op.ProductFamily),
        0
    )


def width_setup_minutes(prev_op, curr_op, width_setup_per_unit):
    if prev_op is None:
        return 0

    if prev_op.Width is None or curr_op.Width is None:
        return 0

    return abs(curr_op.Width - prev_op.Width) * width_setup_per_unit


def temperature_setup_minutes(prev_op, curr_op, per_10_degree_minutes):
    if prev_op is None:
        return 0

    if prev_op.Temperature is None or curr_op.Temperature is None:
        return 0

    diff = abs(curr_op.Temperature - prev_op.Temperature)

    return (diff / 10.0) * per_10_degree_minutes


def calculate_setup(prev_op, curr_op, setup_matrix, params):
    family_setup = family_setup_minutes(prev_op, curr_op, setup_matrix)

    width_setup = width_setup_minutes(
        prev_op,
        curr_op,
        params.WidthSetupPerUnit
    )

    temperature_setup = temperature_setup_minutes(
        prev_op,
        curr_op,
        params.TemperatureSetupPer10DegreeMinutes
    )

    total_setup = family_setup + width_setup + temperature_setup

    return total_setup, family_setup, width_setup, temperature_setup


# =========================================================
# MACHINE UTILITIES
# =========================================================

def get_machine_available_time(machine, planning_start):
    if not machine.Timeline:
        return machine.StartTime or planning_start

    latest_end = max(
        item["EndTime"]
        for item in machine.Timeline
    )

    return latest_end


def get_previous_operation(machine):
    if not machine.Timeline:
        return None

    latest = max(
        machine.Timeline,
        key=lambda x: x["EndTime"]
    )

    return latest["Operation"]


# =========================================================
# BATCH UTILITIES
# =========================================================

def is_heating_operation(operation):
    operation_type = (operation.OperationType or "").lower()

    return (
        "heat" in operation_type
        or "oven" in operation_type
        or "batch" in operation_type
    )


def is_operation_ready(
    operation,
    completed,
    planning_start,
    all_operations=None
):
    previous_seq = operation.SequenceNumber - 1

    if previous_seq <= 0:
        return operation.EarliestStart or planning_start

    previous_key = (
        operation.WorkOrderID,
        previous_seq
    )

    own_ready = completed.get(previous_key)

    if own_ready is None:
        return None

    persistent_batch_id = getattr(
        operation,
        "PersistentBatchID",
        None
    )

    if (
        persistent_batch_id is None
        or all_operations is None
    ):
        return own_ready

    batch_members = [
        op
        for op in all_operations
        if (
            getattr(op, "PersistentBatchID", None)
            == persistent_batch_id
            and op.SequenceNumber
            == operation.SequenceNumber
        )
    ]

    ready_times = []

    for member in batch_members:

        prev_key = (
            member.WorkOrderID,
            previous_seq
        )

        prev_finish = completed.get(prev_key)

        if prev_finish is None:
            return None

        ready_times.append(prev_finish)

    return max(ready_times)



def can_join_new_batch(
    candidate,
    seed_operation,
    machine,
    machine_assignment,
    assigned_machine_id,
    completed,
    planning_start,
    current_batch_operations
):
    if candidate.OperationID == seed_operation.OperationID:
        return False

    if candidate.WorkOrderID == seed_operation.WorkOrderID:
        return False

    if candidate.SequenceNumber != seed_operation.SequenceNumber:
        return False

    if not is_heating_operation(candidate):
        return False

    if not machine_can_process(candidate, machine):
        return False

    ready_time = is_operation_ready(
        candidate,
        completed,
        planning_start
    )


    if ready_time is None:
        print(
            "NOT READY:",
            candidate.WorkOrderID,
            candidate.OperationID,
            candidate.SequenceNumber
        )
        return False

    if candidate.ProductFamily != seed_operation.ProductFamily:
        return False

    if candidate.Temperature != seed_operation.Temperature:
        return False

    total_weight = sum(
        op.Weight or 0
        for op in current_batch_operations
    )

    total_length = sum(
        op.Length or 0
        for op in current_batch_operations
    )

    new_weight = total_weight + (candidate.Weight or 0)
    new_length = total_length + (candidate.Length or 0)

    if machine.MaxWeight is not None and new_weight > machine.MaxWeight:
        return False

    if machine.MaxLength is not None and new_length > machine.MaxLength:
        return False

    return True


def collect_new_batch_operations(
    seed_operation,
    unscheduled,
    machine,
    machine_assignment,
    assigned_machine_id,
    completed,
    planning_start
):
    batch_operations = [seed_operation]


    for candidate in list(unscheduled):


        if can_join_new_batch(
            candidate,
            seed_operation,
            machine,
            machine_assignment,
            assigned_machine_id,
            completed,
            planning_start,
            batch_operations
        ):

            batch_operations.append(candidate)

    return batch_operations


def find_existing_batch(machine, operation, candidate_start):
    return None



# =========================================================
# POST-SCHEDULE OVER-SOAK CHECK
# =========================================================

def check_oversoak_after_scheduling(scheduled_rows, params):
    oversoak_violations = 0
    infeasible_extra = 0

    lookup = {
        (op.WorkOrderID, op.SequenceNumber): op
        for op in scheduled_rows
    }

    for op in scheduled_rows:
        operation_type = (op.OperationType or "").lower()

        is_heating = (
            "heat" in operation_type
            or "oven" in operation_type
            or "batch" in operation_type
        )

        if not is_heating:
            op.OverSoakMinutes = 0
            op.OverSoakViolation = False
            continue

        next_key = (
            op.WorkOrderID,
            op.SequenceNumber + 1
        )

        next_op = lookup.get(next_key)

        if next_op is None:
            op.OverSoakMinutes = 0
            op.OverSoakViolation = False
            continue

        release_time = getattr(
            op,
            "BatchEndTime",
            op.EndTime
        )

        gap_minutes = (
            next_op.StartTime - release_time
        ).total_seconds() / 60

        if gap_minutes < 0:
            gap_minutes = 0

        op.OverSoakMinutes = gap_minutes

        if gap_minutes > params.MaxOverSoakMinutes:
            op.OverSoakViolation = True
            oversoak_violations += 1
            # infeasible_extra += 1
        else:
            op.OverSoakViolation = False

    return infeasible_extra, oversoak_violations


# =========================================================
# OVER-SOAK REPAIR
# =========================================================

def repair_oversoak_by_delaying_work_orders(
    scheduled_rows,
    params,
    calendar_details,
    machines
):
    lookup = {
        (op.WorkOrderID, op.SequenceNumber): op
        for op in scheduled_rows
    }

    machine_lookup = {
        machine_id: machine
        for machine_id, machine in machines.items()
    }

    repaired = False

    for op in scheduled_rows:
        if not getattr(op, "OverSoakViolation", False):
            continue

        next_key = (
            op.WorkOrderID,
            op.SequenceNumber + 1
        )

        next_op = lookup.get(next_key)

        if next_op is None:
            continue

        excess_minutes = (
            op.OverSoakMinutes
            - params.MaxOverSoakMinutes
        )

        if excess_minutes <= 0:
            continue

        delay = timedelta(minutes=excess_minutes)

        machine = machine_lookup.get(op.AssignedMachine)

        if machine is None:
            continue

        proposed_setup_start = op.SetupStart + delay

        total_block_hours = (
            op.SetupMinutes / 60
        ) + op.DurationHours

        new_setup_start = adjust_to_calendar_and_downtime(
            machine,
            calendar_details,
            proposed_setup_start,
            total_block_hours
        )

        shift = new_setup_start - op.SetupStart

        if getattr(op, "BatchID", None):

            batch_id = op.BatchID

            batch_members = [
                x for x in scheduled_rows
                if getattr(x, "BatchID", None) == batch_id
            ]

            for member in batch_members:
                member.SetupStart += shift
                member.StartTime += shift
                member.EndTime += shift

                if hasattr(member, "BatchEndTime"):
                    member.BatchEndTime += shift

        else:

            op.SetupStart += shift
            op.StartTime += shift
            op.EndTime += shift

            if hasattr(op, "BatchEndTime"):
                op.BatchEndTime += shift


        repaired = True

    work_orders = sorted(
        set(op.WorkOrderID for op in scheduled_rows)
    )

    for wo in work_orders:
        wo_ops = sorted(
            [
                op for op in scheduled_rows
                if op.WorkOrderID == wo
            ],
            key=lambda x: x.SequenceNumber
        )

        for i in range(1, len(wo_ops)):
            prev_op = wo_ops[i - 1]
            curr_op = wo_ops[i]

            if curr_op.StartTime < prev_op.EndTime:
                machine = machine_lookup.get(curr_op.AssignedMachine)

                if machine is None:
                    continue

                proposed_setup_start = curr_op.SetupStart + (
                    prev_op.EndTime - curr_op.StartTime
                )

                total_block_hours = (
                    curr_op.SetupMinutes / 60
                ) + curr_op.DurationHours

                new_setup_start = adjust_to_calendar_and_downtime(
                    machine,
                    calendar_details,
                    proposed_setup_start,
                    total_block_hours
                )

                shift = new_setup_start - curr_op.SetupStart

                if getattr(curr_op, "BatchID", None):

                    batch_id = curr_op.BatchID

                    batch_members = [
                        x for x in scheduled_rows
                        if getattr(x, "BatchID", None) == batch_id
                    ]

                    for member in batch_members:
                        member.SetupStart += shift
                        member.StartTime += shift
                        member.EndTime += shift

                        if hasattr(member, "BatchEndTime"):
                            member.BatchEndTime += shift

                else:

                    curr_op.SetupStart += shift
                    curr_op.StartTime += shift
                    curr_op.EndTime += shift

                    if hasattr(curr_op, "BatchEndTime"):
                        curr_op.BatchEndTime += shift


                repaired = True

    return repaired


# =========================================================
# SCHEDULER
# =========================================================

def schedule_operations(operation_order, machine_assignment, scheduling_input):
    operations = deepcopy(operation_order)
    machines = deepcopy(scheduling_input.machines)

    params = scheduling_input.parameters
    planning_start = params.PlanningStart
    setup_matrix = scheduling_input.family_setup_matrix
    calendar_details = scheduling_input.calendar_details

    completed = {}
    scheduled_rows = []
    infeasible_count = 0

    # -----------------------------------------------------
    # GROUP OPERATIONS
    # -----------------------------------------------------

    operations_by_wo = {}

    for op in operations:
        operations_by_wo.setdefault(
            op.WorkOrderID,
            {}
        )[op.SequenceNumber] = op

    work_order_order = []

    for op in operations:
        if op.WorkOrderID not in work_order_order:
            work_order_order.append(op.WorkOrderID)

    remaining_work_orders = work_order_order.copy()

    max_sequence = max(
        op.SequenceNumber
        for op in operations
    )

    # -----------------------------------------------------
    # HELPERS
    # -----------------------------------------------------

    def is_regular_machine(machine):
        return machine.MachineType.lower() == "regular"

    def is_batch_machine(machine):
        return machine.MachineType.lower() != "regular"

    def get_candidate_ovens(op):
        return [
            machine_id
            for machine_id, machine in machines.items()
            if (
                is_batch_machine(machine)
                and machine_can_process(op, machine)
            )
        ]

    def get_candidate_presses(op):
        return [
            machine_id
            for machine_id, machine in machines.items()
            if (
                is_regular_machine(machine)
                and machine_can_process(op, machine)
            )
        ]

    def batch_capacity_ok(batch_ops, machine):
        total_weight = sum(
            op.Weight or 0
            for op in batch_ops
        )

        total_length = sum(
            op.Length or 0
            for op in batch_ops
        )

        if (
            machine.MaxWeight is not None
            and total_weight > machine.MaxWeight
        ):
            return False

        if (
            machine.MaxLength is not None
            and total_length > machine.MaxLength
        ):
            return False

        return True

    def compatible_with_seed(candidate, seed):
        if candidate is None:
            return False

        if not is_heating_operation(candidate):
            return False

        if candidate.ProductFamily != seed.ProductFamily:
            return False

        if candidate.Temperature != seed.Temperature:
            return False

        return True

    def wo_can_use_oven_for_all_heating(work_order_id, oven):
        wo_ops = operations_by_wo[work_order_id]

        for op in wo_ops.values():
            if is_heating_operation(op):
                if not machine_can_process(op, oven):
                    return False

        return True

    def choose_batch_for_seed(seed_wo):
        seed_op = operations_by_wo[seed_wo].get(1)

        if seed_op is None:
            raise ValueError(
                f"Missing OP1 for work order {seed_wo}"
            )

        if not is_heating_operation(seed_op):
            raise ValueError(
                f"OP1 must be heating for work order {seed_wo}"
            )

        candidate_ovens = get_candidate_ovens(seed_op)

        if not candidate_ovens:
            raise ValueError(
                f"No feasible oven for {seed_op.OperationID}"
            )

        best_choice = None

        for oven_id in candidate_ovens:
            oven = machines[oven_id]

            batch_wos = []
            batch_ops = []

            for wo in remaining_work_orders:
                candidate_op = operations_by_wo[wo].get(1)

                if not compatible_with_seed(
                    candidate_op,
                    seed_op
                ):
                    continue

                if not wo_can_use_oven_for_all_heating(
                    wo,
                    oven
                ):
                    continue

                trial_ops = batch_ops + [candidate_op]

                if not batch_capacity_ok(
                    trial_ops,
                    oven
                ):
                    continue

                batch_wos.append(wo)
                batch_ops.append(candidate_op)

            if seed_wo not in batch_wos:
                continue

            oven_available = get_machine_available_time(
                oven,
                planning_start
            )

            score = (
                -len(batch_wos),
                oven_available,
                oven_id,
            )

            if best_choice is None or score < best_choice[0]:
                best_choice = (
                    score,
                    oven_id,
                    batch_wos,
                )

        if best_choice is None:
            raise ValueError(
                f"Could not create batch for {seed_wo}"
            )

        return best_choice[1], best_choice[2]

    def choose_best_press(op, ready_time):
        candidates = get_candidate_presses(op)

        if not candidates:
            raise ValueError(
                f"No feasible press for {op.OperationID}"
            )

        best = None

        for machine_id in candidates:
            machine = machines[machine_id]

            machine_available = get_machine_available_time(
                machine,
                planning_start
            )

            previous_op = get_previous_operation(machine)

            (
                total_setup,
                family_setup,
                width_setup,
                temp_setup,
            ) = calculate_setup(
                previous_op,
                op,
                setup_matrix,
                params
            )

            earliest_setup_start = max(
                machine_available,
                ready_time
            )

            total_block_hours = (
                total_setup / 60
            ) + op.DurationHours

            setup_start = adjust_to_calendar_and_downtime(
                machine,
                calendar_details,
                earliest_setup_start,
                total_block_hours
            )

            production_start = setup_start + timedelta(
                minutes=total_setup
            )

            production_end = production_start + timedelta(
                hours=op.DurationHours
            )

            score = (
                production_end,
                total_setup,
                machine_id,
            )

            if best is None or score < best[0]:
                best = (
                    score,
                    machine_id,
                    setup_start,
                    production_start,
                    production_end,
                    total_setup,
                    family_setup,
                    width_setup,
                    temp_setup,
                )

        return best

    def schedule_press_operation(op, ready_time, persistent_batch_id):
        (
            _,
            machine_id,
            setup_start,
            production_start,
            production_end,
            total_setup,
            family_setup,
            width_setup,
            temp_setup,
        ) = choose_best_press(op, ready_time)

        machine = machines[machine_id]

        op.AssignedMachine = machine_id
        op.PersistentBatchID = persistent_batch_id

        op.SetupStart = setup_start
        op.StartTime = production_start
        op.EndTime = production_end

        op.SetupMinutes = total_setup
        op.FamilySetupMinutes = family_setup
        op.WidthSetupMinutes = width_setup
        op.TemperatureSetupMinutes = temp_setup

        op.OverSoakMinutes = 0
        op.OverSoakViolation = False

        due_end = op.DueDate + timedelta(days=1)
        op.Late = production_end > due_end
        op.LatePenalty = (
            params.LateOrderPenalty
            if op.Late
            else 0
        )

        machine.Timeline.append({
            "Operation": op,
            "SetupStart": setup_start,
            "StartTime": production_start,
            "EndTime": production_end,
        })

        completed[
            (
                op.WorkOrderID,
                op.SequenceNumber
            )
        ] = production_end

        scheduled_rows.append(op)

        return production_end

    def schedule_heating_batch(
        batch_wos,
        sequence_number,
        oven_id,
        batch_id,
        persistent_batch_id
    ):
        oven = machines[oven_id]

        batch_ops = [
            operations_by_wo[wo][sequence_number]
            for wo in batch_wos
            if sequence_number in operations_by_wo[wo]
        ]

        if not batch_ops:
            return None

        representative = batch_ops[0]

        ready_times = []

        for op in batch_ops:
            if sequence_number <= 1:
                ready_time = op.EarliestStart or planning_start
            else:
                previous_key = (
                    op.WorkOrderID,
                    sequence_number - 1
                )

                ready_time = completed.get(previous_key)

                if ready_time is None:
                    raise ValueError(
                        f"{op.OperationID} is not ready"
                    )

            ready_times.append(ready_time)

        batch_ready_time = max(ready_times)

        previous_op = get_previous_operation(oven)

        (
            total_setup,
            family_setup,
            width_setup,
            temp_setup,
        ) = calculate_setup(
            previous_op,
            representative,
            setup_matrix,
            params
        )

        machine_available = get_machine_available_time(
            oven,
            planning_start
        )

        earliest_setup_start = max(
            machine_available,
            batch_ready_time
        )

        max_duration = max(
            op.DurationHours
            for op in batch_ops
        )

        total_block_hours = (
            total_setup / 60
        ) + max_duration

        setup_start = adjust_to_calendar_and_downtime(
            oven,
            calendar_details,
            earliest_setup_start,
            total_block_hours
        )

        production_start = setup_start + timedelta(
            minutes=total_setup
        )

        heating_end = production_start + timedelta(
            hours=max_duration
        )

        for op in batch_ops:
            op.BatchID = f"{batch_id}_SEQ{sequence_number}"
            op.PersistentBatchID = persistent_batch_id
            op.AssignedMachine = oven_id

            op.SetupStart = setup_start
            op.StartTime = production_start
            op.EndTime = production_start + timedelta(
                hours=op.DurationHours
            )

            op.SetupMinutes = (
                total_setup
                if op is representative
                else 0
            )

            op.FamilySetupMinutes = (
                family_setup
                if op is representative
                else 0
            )

            op.WidthSetupMinutes = (
                width_setup
                if op is representative
                else 0
            )

            op.TemperatureSetupMinutes = (
                temp_setup
                if op is representative
                else 0
            )

            op.OverSoakMinutes = 0
            op.OverSoakViolation = False

            completed[
                (
                    op.WorkOrderID,
                    op.SequenceNumber
                )
            ] = op.EndTime

            scheduled_rows.append(op)

        return {
            "oven": oven,
            "batch_ops": batch_ops,
            "setup_start": setup_start,
            "production_start": production_start,
            "heating_end": heating_end,
            "representative": representative,
        }

    # -----------------------------------------------------
    # MAIN BATCH-CAMPAIGN SCHEDULER
    # -----------------------------------------------------

    campaign_counter = 1

    while remaining_work_orders:
        seed_wo = remaining_work_orders[0]

        oven_id, batch_wos = choose_batch_for_seed(
            seed_wo
        )

        batch_id = f"BATCH_{campaign_counter}"
        persistent_batch_id = f"PBATCH_{campaign_counter}"

        print(
            "\nSTARTING BATCH",
            batch_id,
            "OVEN",
            oven_id,
            "WOs",
            batch_wos,
        )

        campaign_counter += 1

        # Freeze membership for the whole route
        for wo in batch_wos:
            for op in operations_by_wo[wo].values():
                op.PersistentBatchID = persistent_batch_id

        sequence_number = 1

        while sequence_number <= max_sequence:
            sample_op = None

            for wo in batch_wos:
                sample_op = operations_by_wo[wo].get(
                    sequence_number
                )

                if sample_op is not None:
                    break

            if sample_op is None:
                sequence_number += 1
                continue

            if is_heating_operation(sample_op):
                heating_result = schedule_heating_batch(
                    batch_wos=batch_wos,
                    sequence_number=sequence_number,
                    oven_id=oven_id,
                    batch_id=batch_id,
                    persistent_batch_id=persistent_batch_id,
                )

                next_sequence = sequence_number + 1

                if (
                    next_sequence <= max_sequence
                    and any(
                        next_sequence in operations_by_wo[wo]
                        for wo in batch_wos
                    )
                ):
                    press_end_times = []

                    for wo in batch_wos:
                        press_op = operations_by_wo[wo].get(
                            next_sequence
                        )

                        if press_op is None:
                            continue

                        press_ready = completed[
                            (
                                press_op.WorkOrderID,
                                sequence_number
                            )
                        ]

                        press_end = schedule_press_operation(
                            press_op,
                            press_ready,
                            persistent_batch_id,
                        )

                        press_end_times.append(press_end)

                    batch_release_time = max(
                        press_end_times
                    )

                    for op in heating_result["batch_ops"]:
                        op.BatchEndTime = batch_release_time

                    heating_result["oven"].Timeline.append({
                        "Operation":
                            heating_result["representative"],
                        "SetupStart":
                            heating_result["setup_start"],
                        "StartTime":
                            heating_result["production_start"],
                        "HeatingEndTime":
                            heating_result["heating_end"],
                        "EndTime":
                            batch_release_time,
                        "BatchID":
                            f"{batch_id}_SEQ{sequence_number}",
                        "PersistentBatchID":
                            persistent_batch_id,
                        "BatchOperations":
                            heating_result["batch_ops"],
                    })

                    sequence_number += 2

                else:
                    batch_release_time = heating_result[
                        "heating_end"
                    ]

                    for op in heating_result["batch_ops"]:
                        op.BatchEndTime = batch_release_time

                    heating_result["oven"].Timeline.append({
                        "Operation":
                            heating_result["representative"],
                        "SetupStart":
                            heating_result["setup_start"],
                        "StartTime":
                            heating_result["production_start"],
                        "HeatingEndTime":
                            heating_result["heating_end"],
                        "EndTime":
                            batch_release_time,
                        "BatchID":
                            f"{batch_id}_SEQ{sequence_number}",
                        "PersistentBatchID":
                            persistent_batch_id,
                        "BatchOperations":
                            heating_result["batch_ops"],
                    })

                    sequence_number += 1

            else:
                # Fallback for unexpected non-heating operation
                # not directly after a heating step.
                for wo in batch_wos:
                    op = operations_by_wo[wo].get(
                        sequence_number
                    )

                    if op is None:
                        continue

                    previous_key = (
                        op.WorkOrderID,
                        sequence_number - 1
                    )

                    ready_time = completed.get(
                        previous_key,
                        op.EarliestStart or planning_start
                    )

                    schedule_press_operation(
                        op,
                        ready_time,
                        persistent_batch_id,
                    )

                sequence_number += 1

        for wo in batch_wos:
            if wo in remaining_work_orders:
                remaining_work_orders.remove(wo)

        print(
            "FINISHED BATCH",
            batch_id,
            "WOs",
            batch_wos,
        )

    # -----------------------------------------------------
    # POST CHECKS
    # -----------------------------------------------------

    infeasible_extra, oversoak_violations = (
        check_oversoak_after_scheduling(
            scheduled_rows,
            params
        )
    )

    print("\n========== BATCH SUMMARY ==========\n")

    batches = {}

    for row in scheduled_rows:
        if getattr(row, "BatchID", None):
            batches.setdefault(
                row.BatchID,
                []
            ).append(row)

    for batch_id, rows in batches.items():
        print(
            batch_id,
            "WO count:",
            len(
                set(
                    str(r.WorkOrderID)
                    for r in rows
                )
            ),
            "WOs:",
            sorted(
                set(
                    str(r.WorkOrderID)
                    for r in rows
                )
            ),
            "Start:",
            min(r.StartTime for r in rows),
            "BatchEnd:",
            max(
                getattr(
                    r,
                    "BatchEndTime",
                    r.EndTime
                )
                for r in rows
            )
        )

    batch_sizes = {}

    for op in scheduled_rows:
        if getattr(op, "BatchID", None):
            batch_sizes.setdefault(
                op.BatchID,
                set()
            ).add(op.WorkOrderID)

    print("\n===== BATCH KPI =====")

    sizes = [
        len(v)
        for v in batch_sizes.values()
    ]

    if sizes:
        print("Batches:", len(sizes))
        print(
            "Average Size:",
            sum(sizes) / len(sizes)
        )
        print("Largest Batch:", max(sizes))
    else:
        print("Batches:", 0)
        print("Average Size:", 0)
        print("Largest Batch:", 0)

    return (
        scheduled_rows,
        machines,
        infeasible_count,
        oversoak_violations,
    )

