# machine_engine.py
"""
PlanWise scheduling engine.

Design goals
------------
1. Preserve the public API used by genetic_algorithm.py:
       schedule_operations(operation_order, machine_assignment, scheduling_input)
2. Build persistent campaigns/batches once.
3. Keep each persistent campaign on one oven until its complete route finishes.
4. Schedule campaign events by readiness while allowing different ovens and
   presses to operate concurrently on independent machine timelines.
5. Keep each work order's HeatingEndTime / BatchEndTime / ReleaseTime separate.
6. Treat an oven as occupied until the final member of its batch leaves for the
   next operation.
7. Respect machine capability, batch capacity, calendars, downtime, setup,
   precedence and maximum over-soak.

The implementation intentionally avoids post-schedule time shifting. Resource
reservations are created once and remain internally consistent.
"""

from copy import deepcopy
from datetime import datetime, timedelta

from constraints import machine_can_process
from calendar_utils import adjust_to_calendar

from campaign_engine import CampaignBuilder
from constraint_engine import ConstraintEngine
from timeline_engine import TimelineManager

from oven_engine import OvenEngine


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
    downtimes = getattr(machine, "Downtimes", []) or []
    if not downtimes:
        return proposed_start

    duration = timedelta(hours=total_block_hours)
    current_start = proposed_start

    # Re-check after every move because moving beyond one downtime may enter
    # another downtime window.
    for _ in range(100):
        current_end = current_start + duration
        moved = False

        for downtime in downtimes:
            downtime_start = parse_datetime(downtime.get("StartTime"))
            downtime_end = parse_datetime(downtime.get("EndTime"))

            if (
                downtime_start is None
                or downtime_end is None
                or downtime_end <= downtime_start
            ):
                continue

            if block_overlaps(
                current_start,
                current_end,
                downtime_start,
                downtime_end,
            ):
                current_start = downtime_end
                moved = True
                break

        if not moved:
            return current_start

    return current_start


def adjust_to_calendar_and_downtime(
    machine,
    calendar_details,
    proposed_start,
    total_block_hours,
):
    current_start = proposed_start

    for _ in range(100):
        calendar_start = adjust_to_calendar(
            machine,
            calendar_details,
            current_start,
            total_block_hours,
        )

        downtime_start = adjust_to_machine_downtime(
            machine,
            calendar_start,
            total_block_hours,
        )

        if downtime_start == calendar_start:
            return downtime_start

        current_start = downtime_start

    return current_start


# =========================================================
# SETUP CALCULATIONS
# =========================================================


def family_setup_minutes(prev_op, curr_op, setup_matrix):
    if prev_op is None:
        return 0
    if not getattr(prev_op, "ProductFamily", None):
        return 0
    if not getattr(curr_op, "ProductFamily", None):
        return 0
    if prev_op.ProductFamily == curr_op.ProductFamily:
        return 0

    return setup_matrix.get(
        (prev_op.ProductFamily, curr_op.ProductFamily),
        0,
    )


def width_setup_minutes(prev_op, curr_op, width_setup_per_unit):
    if prev_op is None:
        return 0
    if getattr(prev_op, "Width", None) is None:
        return 0
    if getattr(curr_op, "Width", None) is None:
        return 0

    return abs(curr_op.Width - prev_op.Width) * width_setup_per_unit


def temperature_setup_minutes(prev_op, curr_op, per_10_degree_minutes):
    if prev_op is None:
        return 0
    if getattr(prev_op, "Temperature", None) is None:
        return 0
    if getattr(curr_op, "Temperature", None) is None:
        return 0

    diff = abs(curr_op.Temperature - prev_op.Temperature)
    return (diff / 10.0) * per_10_degree_minutes


def calculate_setup(
    prev_op,
    curr_op,
    setup_matrix,
    params,
):
    family_setup = family_setup_minutes(
        prev_op,
        curr_op,
        setup_matrix,
    )

    width_setup = width_setup_minutes(
        prev_op,
        curr_op,
        params.WidthSetupPerUnit,
    )

    temperature_setup = temperature_setup_minutes(
        prev_op,
        curr_op,
        params.TemperatureSetupPer10DegreeMinutes,
    )

    # -----------------------------------------------------
    # SETUP RULE
    #
    # Setup effects occur in parallel / overlap.
    # Therefore only the longest applicable setup governs
    # the physical setup duration.
    # -----------------------------------------------------
    total_setup = max(
        family_setup,
        width_setup,
        temperature_setup,
    )

    return (
        total_setup,
        family_setup,
        width_setup,
        temperature_setup,
    )

# def calculate_setup(prev_op, curr_op, setup_matrix, params):
#     family_setup = family_setup_minutes(prev_op, curr_op, setup_matrix)
#     width_setup = width_setup_minutes(
#         prev_op,
#         curr_op,
#         params.WidthSetupPerUnit,
#     )
#     temperature_setup = temperature_setup_minutes(
#         prev_op,
#         curr_op,
#         params.TemperatureSetupPer10DegreeMinutes,
#     )

#     total_setup = family_setup + width_setup + temperature_setup
#     return total_setup, family_setup, width_setup, temperature_setup


# =========================================================
# MACHINE / TIMELINE UTILITIES
# =========================================================


def _timeline_start(item):
    return item.get("SetupStart") or item.get("StartTime")


def _timeline_end(item):
    return item.get("EndTime")


def _sorted_timeline(machine):
    return sorted(
        [
            item
            for item in (getattr(machine, "Timeline", []) or [])
            if _timeline_start(item) is not None and _timeline_end(item) is not None
        ],
        key=_timeline_start,
    )


def get_machine_available_time(machine, planning_start):
    timeline = _sorted_timeline(machine)
    if not timeline:
        return getattr(machine, "StartTime", None) or planning_start
    return max(item["EndTime"] for item in timeline)


def get_previous_operation(machine, before_time=None):
    timeline = _sorted_timeline(machine)
    if before_time is not None:
        timeline = [item for item in timeline if item["EndTime"] <= before_time]
    if not timeline:
        return None
    return max(timeline, key=lambda item: item["EndTime"])["Operation"]


def find_earliest_machine_slot(
    machine,
    planning_start,
    ready_time,
    total_block_hours,
    calendar_details,
):
    """Find the first feasible setup+production block, including internal gaps."""

    duration = timedelta(hours=total_block_hours)
    candidate_start = max(
        planning_start,
        ready_time,
        getattr(machine, "StartTime", None) or planning_start,
    )

    timeline = _sorted_timeline(machine)

    for item in timeline:
        occupied_start = _timeline_start(item)
        occupied_end = item["EndTime"]

        candidate_start = adjust_to_calendar_and_downtime(
            machine,
            calendar_details,
            candidate_start,
            total_block_hours,
        )
        candidate_end = candidate_start + duration

        if candidate_end <= occupied_start:
            return candidate_start

        if candidate_start < occupied_end:
            candidate_start = occupied_end

    return adjust_to_calendar_and_downtime(
        machine,
        calendar_details,
        candidate_start,
        total_block_hours,
    )


def _find_slot_near_target(
    machine,
    planning_start,
    ready_time,
    target_start,
    total_block_hours,
    calendar_details,
):
    """
    Prefer a slot around target_start, but never earlier than material readiness.

    This is used for JIT heating. It still searches the complete timeline and
    therefore cannot overlap an existing reservation.
    """

    desired = max(
        planning_start,
        ready_time,
        getattr(machine, "StartTime", None) or planning_start,
        target_start,
    )

    return find_earliest_machine_slot(
        machine,
        planning_start,
        desired,
        total_block_hours,
        calendar_details,
    )


def _insert_timeline(machine, item):
    machine.Timeline.append(item)
    machine.Timeline.sort(key=lambda x: _timeline_start(x) or x["StartTime"])


# =========================================================
# OPERATION / BATCH UTILITIES
# =========================================================


def is_heating_operation(operation):
    operation_type = (getattr(operation, "OperationType", None) or "").lower()
    return (
        "heat" in operation_type
        or "oven" in operation_type
        or "batch" in operation_type
    )


def is_operation_ready(
    operation,
    completed,
    planning_start,
    all_operations=None,
):
    previous_seq = operation.SequenceNumber - 1
    if previous_seq <= 0:
        return operation.EarliestStart or planning_start

    own_ready = completed.get((operation.WorkOrderID, previous_seq))
    if own_ready is None:
        return None

    persistent_batch_id = getattr(operation, "PersistentBatchID", None)
    if persistent_batch_id is None or all_operations is None:
        return own_ready

    batch_members = [
        op
        for op in all_operations
        if (
            getattr(op, "PersistentBatchID", None) == persistent_batch_id
            and op.SequenceNumber == operation.SequenceNumber
        )
    ]

    ready_times = []
    for member in batch_members:
        prev_finish = completed.get((member.WorkOrderID, previous_seq))
        if prev_finish is None:
            return None
        ready_times.append(prev_finish)

    return max(ready_times) if ready_times else own_ready


def can_join_new_batch(
    candidate,
    seed_operation,
    machine,
    machine_assignment,
    assigned_machine_id,
    completed,
    planning_start,
    current_batch_operations,
):
    """Compatibility helper retained for backwards compatibility."""

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

    if candidate.ProductFamily != seed_operation.ProductFamily:
        return False
    if candidate.Temperature != seed_operation.Temperature:
        return False

    total_weight = sum((op.Weight or 0) for op in current_batch_operations)
    total_length = sum((op.Length or 0) for op in current_batch_operations)

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
    planning_start,
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
            batch_operations,
        ):
            batch_operations.append(candidate)

    return batch_operations


def find_existing_batch(machine, operation, candidate_start):
    # Dynamic joining of an already-started furnace batch is intentionally not
    # supported in this engine. Batch membership is frozen at campaign build.
    return None


# =========================================================
# VALIDATION
# =========================================================


def check_oversoak_after_scheduling(scheduled_rows, params):
    oversoak_violations = 0
    infeasible_extra = 0

    lookup = {
        (op.WorkOrderID, op.SequenceNumber): op
        for op in scheduled_rows
    }

    for op in scheduled_rows:
        if not is_heating_operation(op):
            op.OverSoakMinutes = 0
            op.OverSoakViolation = False
            continue

        next_op = lookup.get((op.WorkOrderID, op.SequenceNumber + 1))
        if next_op is None:
            op.OverSoakMinutes = 0
            op.OverSoakViolation = False
            continue

        heating_end = getattr(op, "HeatingEndTime", None) or op.EndTime
        if heating_end is None or next_op.StartTime is None:
            op.OverSoakMinutes = 0
            op.OverSoakViolation = False
            continue

        gap_minutes = max(
            0.0,
            (next_op.StartTime - heating_end).total_seconds() / 60.0,
        )

        op.OverSoakMinutes = gap_minutes
        op.OverSoakViolation = gap_minutes > params.MaxOverSoakMinutes

        if op.OverSoakViolation:
            oversoak_violations += 1

    return infeasible_extra, oversoak_violations


def repair_oversoak_by_delaying_work_orders(
    scheduled_rows,
    params,
    calendar_details,
    machines,
):
    """
    Retained for API compatibility.

    The rewritten engine does not perform unsafe post-schedule shifting because
    that can invalidate already-created machine timelines. Over-soak is handled
    during wave planning and then validated. Returning False explicitly tells
    callers that no post-processing mutation occurred.
    """

    return False


# =========================================================
# CORE SCHEDULER
# =========================================================


def schedule_operations(operation_order, machine_assignment, scheduling_input):
    operations = deepcopy(operation_order)
    machines = deepcopy(scheduling_input.machines)

    params = scheduling_input.parameters
    planning_start = params.PlanningStart
    setup_matrix = scheduling_input.family_setup_matrix
    calendar_details = scheduling_input.calendar_details


    constraint_engine = ConstraintEngine()

    timeline = TimelineManager(
        machines=machines,
        calendar_details=calendar_details,
    )

    timeline.clear_non_fixed()

    # Start every evaluation with clean resource timelines. If the input model
    # intentionally contains fixed reservations, keep only items explicitly
    # marked as fixed/manual.
    for machine in machines.values():
        existing = getattr(machine, "Timeline", []) or []
        fixed = [
            item
            for item in existing
            if item.get("IsFixed") or item.get("IsManual")
        ]
        machine.Timeline = fixed

    completed = {}
    scheduled_rows = []
    infeasible_count = 0

    operations_by_wo = {}
    work_order_order = []

    for op in operations:
        operations_by_wo.setdefault(op.WorkOrderID, {})[op.SequenceNumber] = op
        if op.WorkOrderID not in work_order_order:
            work_order_order.append(op.WorkOrderID)

    if not operations:
        return scheduled_rows, machines, 0, 0

    max_sequence = max(op.SequenceNumber for op in operations)

    # -----------------------------------------------------
    # MACHINE CLASSIFICATION
    # -----------------------------------------------------

    def is_regular_machine(machine):
        return (machine.MachineType or "").lower() == "regular"

    def is_batch_machine(machine):
        return not is_regular_machine(machine)

    def get_candidate_ovens(op):
        return [
            machine_id
            for machine_id, machine in machines.items()
            if is_batch_machine(machine) and machine_can_process(op, machine)
        ]

    def get_candidate_presses(op):
        return [
            machine_id
            for machine_id, machine in machines.items()
            if is_regular_machine(machine) and machine_can_process(op, machine)
        ]

    def batch_capacity_ok(batch_ops, machine):
        total_weight = sum((op.Weight or 0) for op in batch_ops)
        total_length = sum((op.Length or 0) for op in batch_ops)

        if machine.MaxWeight is not None and total_weight > machine.MaxWeight:
            return False
        if machine.MaxLength is not None and total_length > machine.MaxLength:
            return False
        return True

    def compatible_with_seed(candidate, seed):
        if candidate is None or not is_heating_operation(candidate):
            return False
        if candidate.ProductFamily != seed.ProductFamily:
            return False
        if candidate.Temperature != seed.Temperature:
            return False
        return True

    # -----------------------------------------------------
    # BUILD PERSISTENT CAMPAIGNS
    # -----------------------------------------------------


    campaign_builder = CampaignBuilder(
        machines=machines,
        machine_assignment=machine_assignment,
        constraint_engine=constraint_engine,
    )

    campaign_objects = campaign_builder.build(
        work_order_order,
        operations_by_wo,
    )

    campaign_builder.apply_persistent_ids(
        campaign_objects,
        operations_by_wo,
    )

    campaigns = [
        {
            "batch_wos": list(c.work_order_ids),
            "batch_id": c.campaign_id,
            "persistent_batch_id": c.persistent_batch_id,
            "preferred_oven_id": c.preferred_oven_id,
        }
        for c in campaign_objects
    ]


       

    # -----------------------------------------------------
    # PRESS DECISION / RESERVATION
    # -----------------------------------------------------

    def choose_best_press(op, material_ready_time):
        candidate_ids = get_candidate_presses(op)
        if not candidate_ids:
            raise ValueError(f"No feasible press for {op.OperationID}")
            

        best = None
        best_score = None

        for machine_id in candidate_ids:
            machine = machines[machine_id]

            # Setup depends on the operation immediately before the selected
            # slot, not necessarily the globally latest operation.
            rough_ready = max(
                planning_start,
                getattr(machine, "StartTime", None) or planning_start,
            )
            rough_prev = get_previous_operation(machine, rough_ready)
            rough_setup, _, _, _ = calculate_setup(
                rough_prev,
                op,
                setup_matrix,
                params,
            )

            # First locate a feasible setup start. Setup may happen before the
            # hot material arrives, but production cannot start before ready.
            total_block_hours = (rough_setup / 60.0) + op.DurationHours
            setup_start = find_earliest_machine_slot(
                machine,
                planning_start,
                rough_ready,
                total_block_hours,
                calendar_details,
            )

            previous_op = get_previous_operation(machine, setup_start)
            (
                total_setup,
                family_setup,
                width_setup,
                temp_setup,
            ) = calculate_setup(previous_op, op, setup_matrix, params)

            # Re-run with the actual setup duration.
            total_block_hours = (total_setup / 60.0) + op.DurationHours
            setup_start = find_earliest_machine_slot(
                machine,
                planning_start,
                rough_ready,
                total_block_hours,
                calendar_details,
            )

            setup_complete = setup_start + timedelta(minutes=total_setup)
            production_start = max(setup_complete, material_ready_time)

            # If material readiness pushes production beyond the current block,
            # relocate the complete setup+production reservation so it does not
            # overlap a later press reservation.
            if production_start > setup_complete:
                desired_setup = production_start - timedelta(minutes=total_setup)
                setup_start = find_earliest_machine_slot(
                    machine,
                    planning_start,
                    desired_setup,
                    total_block_hours,
                    calendar_details,
                )
                setup_complete = setup_start + timedelta(minutes=total_setup)
                production_start = max(setup_complete, material_ready_time)

            production_end = production_start + timedelta(hours=op.DurationHours)
            waiting_minutes = max(
                0.0,
                (production_start - material_ready_time).total_seconds() / 60.0,
            )

            assignment_penalty = (
                0
                if machine_assignment.get(op.OperationID) in (None, machine_id)
                else 1
            )

            score = (
                waiting_minutes,
                production_end,
                total_setup,
                assignment_penalty,
                machine_id,
            )

            if best_score is None or score < best_score:
                best_score = score
                best = {
                    "MachineID": machine_id,
                    "SetupStart": setup_start,
                    "ProductionStart": production_start,
                    "ProductionEnd": production_end,
                    "SetupMinutes": total_setup,
                    "FamilySetupMinutes": family_setup,
                    "WidthSetupMinutes": width_setup,
                    "TemperatureSetupMinutes": temp_setup,
                    "WaitingMinutes": waiting_minutes,
                }

        return best
    
    def predict_press_start(next_op, heating_end):
        if next_op is None or is_heating_operation(next_op):
            return None

        decision = choose_best_press(
            next_op,
            heating_end,
        )

        if decision is None:
            return None

        return decision["ProductionStart"]

    def commit_press_operation(op, ready_time, persistent_batch_id):
        decision = choose_best_press(op, ready_time)
        if decision is None:
            raise RuntimeError(f"No feasible press found for {op.OperationID}")

        machine_id = decision["MachineID"]
        machine = machines[machine_id]

        op.AssignedMachine = machine_id
        op.PersistentBatchID = persistent_batch_id
        op.SetupStart = decision["SetupStart"]
        op.StartTime = decision["ProductionStart"]
        op.EndTime = decision["ProductionEnd"]
        op.HeatingEndTime = ready_time
        op.ReleaseTime = op.StartTime
        op.BatchEndTime = None

        op.SetupMinutes = decision["SetupMinutes"]
        op.FamilySetupMinutes = decision["FamilySetupMinutes"]
        op.WidthSetupMinutes = decision["WidthSetupMinutes"]
        op.TemperatureSetupMinutes = decision["TemperatureSetupMinutes"]
        op.WaitingMinutes = decision["WaitingMinutes"]
        op.OverSoakMinutes = 0
        op.OverSoakViolation = False

        due_end = op.DueDate + timedelta(days=1)
        op.Late = op.EndTime > due_end
        op.LatePenalty = params.LateOrderPenalty if op.Late else 0

        _insert_timeline(
            machine,
            {
                "Operation": op,
                "SetupStart": op.SetupStart,
                "StartTime": op.StartTime,
                "EndTime": op.EndTime,
            },
        )

        completed[(op.WorkOrderID, op.SequenceNumber)] = op.EndTime
        scheduled_rows.append(op)
        return decision

    oven_engine = OvenEngine(
        machines=machines,
        machine_assignment=machine_assignment,
        params=params,
        planning_start=planning_start,
        setup_matrix=setup_matrix,
        calendar_details=calendar_details,
        operations_by_wo=operations_by_wo,
        completed=completed,
        scheduled_rows=scheduled_rows,
        timeline=timeline,
        constraint_engine=constraint_engine,

        calculate_setup=calculate_setup,
        find_earliest_machine_slot=find_earliest_machine_slot,
        get_previous_operation=get_previous_operation,
        get_candidate_ovens=get_candidate_ovens,
        is_heating_operation=is_heating_operation,
        predict_press_start=predict_press_start,
    )
    

    # -----------------------------------------------------
    # CAMPAIGN-CONTINUITY SCHEDULER
    # -----------------------------------------------------
    #
    # Each persistent campaign owns one oven until its whole route
    # is complete. Different campaigns on different ovens can still
    # run in parallel because every machine timeline is independent.
    # -----------------------------------------------------

    def campaign_can_use_oven(campaign, oven_id):
        oven = machines[oven_id]

        if not is_batch_machine(oven):
            return False

        for wo in campaign["batch_wos"]:
            for op in operations_by_wo[wo].values():
                if not is_heating_operation(op):
                    continue

                if not constraint_engine.machine_can_process(
                    op,
                    oven,
                ):
                    return False

        heating_sequences = sorted({
            op.SequenceNumber
            for wo in campaign["batch_wos"]
            for op in operations_by_wo[wo].values()
            if is_heating_operation(op)
        })

        for seq in heating_sequences:
            seq_ops = [
                operations_by_wo[wo].get(seq)
                for wo in campaign["batch_wos"]
            ]

            seq_ops = [
                op
                for op in seq_ops
                if (
                    op is not None
                    and is_heating_operation(op)
                )
            ]

            if (
                seq_ops
                and not constraint_engine.batch_capacity_ok(
                    seq_ops,
                    oven,
                )
            ):
                return False

        return True


    def campaign_first_ready_time(campaign):
        ready_times = []

        for wo in campaign["batch_wos"]:
            first_op = operations_by_wo[wo].get(1)

            if first_op is None:
                continue

            ready_times.append(
                first_op.EarliestStart
                or planning_start
            )

        return (
            max(ready_times)
            if ready_times
            else planning_start
        )


    def campaign_next_ready_time(
        campaign,
        sequence_number,
    ):
        ready_times = []

        for wo in campaign["batch_wos"]:
            op = operations_by_wo[wo].get(
                sequence_number
            )

            if op is None:
                continue

            if sequence_number <= 1:
                ready = (
                    op.EarliestStart
                    or planning_start
                )
            else:
                ready = completed.get(
                    (
                        op.WorkOrderID,
                        sequence_number - 1,
                    )
                )

            if ready is not None:
                ready_times.append(
                    ready
                )

        return (
            max(ready_times)
            if ready_times
            else planning_start
        )


    oven_ids = sorted(
        machine_id
        for machine_id, machine in machines.items()
        if is_batch_machine(machine)
    )

    oven_owner = {
        oven_id: None
        for oven_id in oven_ids
    }

    campaign_states = []

    for priority, campaign in enumerate(campaigns):
        first_sequence = min(
            (
                op.SequenceNumber
                for wo in campaign["batch_wos"]
                for op in operations_by_wo[wo].values()
            ),
            default=1,
        )

        campaign_states.append({
            "campaign": campaign,
            "priority": priority,
            "next_sequence": first_sequence,
            "ready_time": campaign_first_ready_time(
                campaign
            ),
            "active": False,
            "done": False,
            "locked_oven_id": None,
        })


    def available_ovens_for_campaign(campaign):
        feasible = [
            oven_id
            for oven_id in oven_ids
            if (
                oven_owner[oven_id] is None
                and campaign_can_use_oven(
                    campaign,
                    oven_id,
                )
            )
        ]

        preferred = campaign.get(
            "preferred_oven_id"
        )

        return sorted(
            feasible,
            key=lambda oven_id: (
                0
                if oven_id == preferred
                else 1,

                get_machine_available_time(
                    machines[oven_id],
                    planning_start,
                ),

                oven_id,
            )
        )


    def activate_waiting_campaigns():
        waiting_states = sorted(
            [
                state
                for state in campaign_states
                if (
                    not state["done"]
                    and not state["active"]
                )
            ],
            key=lambda state: (
                state["ready_time"],
                state["priority"],
            ),
        )

        made_assignment = True

        while made_assignment:
            made_assignment = False

            for state in waiting_states:
                if (
                    state["done"]
                    or state["active"]
                ):
                    continue

                campaign = state[
                    "campaign"
                ]

                candidates = (
                    available_ovens_for_campaign(
                        campaign
                    )
                )

                if not candidates:
                    continue

                oven_id = candidates[0]

                oven_owner[
                    oven_id
                ] = campaign[
                    "persistent_batch_id"
                ]

                state[
                    "locked_oven_id"
                ] = oven_id

                state[
                    "active"
                ] = True

                campaign[
                    "locked_oven_id"
                ] = oven_id

                made_assignment = True


    activate_waiting_campaigns()


    while any(
        not state["done"]
        for state in campaign_states
    ):
        active_states = [
            state
            for state in campaign_states
            if (
                state["active"]
                and not state["done"]
            )
        ]

        if not active_states:
            waiting_ids = [
                state["campaign"][
                    "persistent_batch_id"
                ]
                for state in campaign_states
                if not state["done"]
            ]

            raise RuntimeError(
                "No active campaign can be scheduled. "
                f"Waiting campaigns: {waiting_ids}"
            )

        state = min(
            active_states,
            key=lambda item: (
                item["ready_time"],
                item["priority"],
            ),
        )

        campaign = state[
            "campaign"
        ]

        sequence_number = state[
            "next_sequence"
        ]

        if sequence_number > max_sequence:
            state["done"] = True

        else:
            campaign_ops = [
                operations_by_wo[wo].get(
                    sequence_number
                )
                for wo in campaign[
                    "batch_wos"
                ]
            ]

            campaign_ops = [
                op
                for op in campaign_ops
                if op is not None
            ]

            if not campaign_ops:
                state[
                    "next_sequence"
                ] += 1

                state[
                    "ready_time"
                ] = campaign_next_ready_time(
                    campaign,
                    state[
                        "next_sequence"
                    ],
                )

                continue

            sample = campaign_ops[0]

            # =================================================
            # HEATING STAGE
            # =================================================
            if is_heating_operation(sample):
                heating_result = (
                    oven_engine
                    .commit_heating_batch(
                        campaign=campaign,
                        sequence_number=
                            sequence_number,
                    )
                )

                if heating_result is None:
                    raise RuntimeError(
                        f"Heating stage returned None for "
                        f"{campaign['persistent_batch_id']} "
                        f"sequence {sequence_number}"
                    )

                next_sequence = (
                    sequence_number + 1
                )

                next_ops = [
                    operations_by_wo[wo].get(
                        next_sequence
                    )
                    for wo in campaign[
                        "batch_wos"
                    ]
                ]

                next_ops = [
                    op
                    for op in next_ops
                    if op is not None
                ]

                if (
                    next_ops
                    and not is_heating_operation(
                        next_ops[0]
                    )
                ):
                    press_requests = []

                    for op in next_ops:
                        press_requests.append({
                            "op": op,
                            "ready_time":
                                heating_result[
                                    "heating_end"
                                ],
                        })

                    press_requests.sort(
                        key=lambda req: (
                            req["ready_time"],
                            req["op"].DueDate,
                            req["op"].WorkOrderID,
                        )
                    )

                    releases = {}

                    for request in press_requests:
                        op = request["op"]
                        ready_time = request[
                            "ready_time"
                        ]

                        decision = (
                            commit_press_operation(
                                op,
                                ready_time,
                                campaign[
                                    "persistent_batch_id"
                                ],
                            )
                        )

                        releases[
                            op.WorkOrderID
                        ] = decision[
                            "ProductionStart"
                        ]

                    oven_engine.finalize_batch_release(
                        heating_result,
                        releases,
                    )

                    state[
                        "next_sequence"
                    ] = (
                        next_sequence + 1
                    )

                else:
                    oven_engine.finalize_batch_release(
                        heating_result,
                        {},
                    )

                    state[
                        "next_sequence"
                    ] = next_sequence

            # =================================================
            # GENERIC NON-HEATING STAGE
            # =================================================
            else:
                requests = []

                for op in campaign_ops:
                    ready = (
                        op.EarliestStart
                        or planning_start
                        if sequence_number <= 1
                        else completed.get(
                            (
                                op.WorkOrderID,
                                sequence_number - 1,
                            )
                        )
                    )

                    if ready is None:
                        raise ValueError(
                            f"{op.OperationID} "
                            f"is not ready"
                        )

                    requests.append(
                        (
                            ready,
                            op.DueDate,
                            op.WorkOrderID,
                            op,
                        )
                    )

                requests.sort(
                    key=lambda item: (
                        item[0],
                        item[1],
                        item[2],
                    )
                )

                for ready, _, _, op in requests:
                    commit_press_operation(
                        op,
                        ready,
                        campaign[
                            "persistent_batch_id"
                        ],
                    )

                state[
                    "next_sequence"
                ] += 1

            next_seq = state[
                "next_sequence"
            ]

            has_remaining_operation = any(
                any(
                    seq >= next_seq
                    for seq in operations_by_wo[
                        wo
                    ].keys()
                )
                for wo in campaign[
                    "batch_wos"
                ]
            )

            if not has_remaining_operation:
                state["done"] = True

            else:
                state[
                    "ready_time"
                ] = campaign_next_ready_time(
                    campaign,
                    next_seq,
                )

        # -------------------------------------------------
        # RELEASE OVEN ONLY AFTER COMPLETE CAMPAIGN ROUTE
        # -------------------------------------------------
        if state["done"]:
            locked_oven_id = state[
                "locked_oven_id"
            ]

            if locked_oven_id is not None:
                if (
                    oven_owner.get(
                        locked_oven_id
                    )
                    == campaign[
                        "persistent_batch_id"
                    ]
                ):
                    oven_owner[
                        locked_oven_id
                    ] = None

            campaign.pop(
                "locked_oven_id",
                None,
            )

            state[
                "locked_oven_id"
            ] = None

            state[
                "active"
            ] = False

            activate_waiting_campaigns()


    # -----------------------------------------------------
    # FINAL VALIDATION
    # -----------------------------------------------------

    infeasible_extra, oversoak_violations = check_oversoak_after_scheduling(
        scheduled_rows,
        params,
    )
    infeasible_count += infeasible_extra

    # Explicit precedence/resource sanity checks. They do not modify the plan.
    by_wo = {}
    for op in scheduled_rows:
        by_wo.setdefault(op.WorkOrderID, []).append(op)

    for wo_ops in by_wo.values():
        wo_ops.sort(key=lambda op: op.SequenceNumber)
        for prev_op, curr_op in zip(wo_ops, wo_ops[1:]):
            if curr_op.StartTime < prev_op.EndTime:
                infeasible_count += 1

    for machine in machines.values():
        timeline = _sorted_timeline(machine)
        for previous, current in zip(timeline, timeline[1:]):
            if _timeline_start(current) < previous["EndTime"]:
                infeasible_count += 1


    return (
        scheduled_rows,
        machines,
        infeasible_count,
        oversoak_violations,
    )
