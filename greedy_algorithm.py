# greedy_algorithm.py

from constraints import machine_can_process
from machine_engine import schedule_operations
from genetic_algorithm import (
    group_operations_by_work_order,
    expand_work_order_order,
    calculate_oven_utilization,
)


def create_deterministic_machine_assignment(operations, machines):
    assignment = {}

    machine_load_count = {
        machine_id: 0
        for machine_id in machines.keys()
    }

    for op in operations:
        feasible = [
            machine_id
            for machine_id, machine in machines.items()
            if machine_can_process(op, machine)
        ]

        if not feasible:
            raise ValueError(f"No feasible machine found for {op.OperationID}")

        chosen_machine = min(
            feasible,
            key=lambda m: machine_load_count[m]
        )

        assignment[op.OperationID] = chosen_machine
        machine_load_count[chosen_machine] += 1

    return assignment


def evaluate_work_order_order(work_order_order, scheduling_input, grouped_operations, assignment):
    expanded_order = expand_work_order_order(
        work_order_order,
        grouped_operations,
    )

    scheduled_ops, machines, infeasible_count, oversoak_violations = schedule_operations(
        expanded_order,
        assignment,
        scheduling_input,
    )

    late_orders = sum(1 for op in scheduled_ops if op.Late)
    late_penalty = sum(op.LatePenalty for op in scheduled_ops)

    total_setup = sum(op.SetupMinutes for op in scheduled_ops)
    family_setup = sum(op.FamilySetupMinutes for op in scheduled_ops)
    width_setup = sum(op.WidthSetupMinutes for op in scheduled_ops)
    temperature_setup = sum(op.TemperatureSetupMinutes for op in scheduled_ops)

    total_cost = total_setup + late_penalty
    oven_utilization = calculate_oven_utilization(machines)

    fitness = (
        infeasible_count,
        oversoak_violations,
        late_orders,
        late_penalty,
        -oven_utilization,
        total_setup,
        total_cost,
    )

    return {
        "fitness": fitness,
        "scheduled_ops": scheduled_ops,
        "machines": machines,
        "infeasible_count": infeasible_count,
        "oversoak_violations": oversoak_violations,
        "late_orders": late_orders,
        "late_penalty": late_penalty,
        "setup": total_setup,
        "family_setup": family_setup,
        "width_setup": width_setup,
        "temperature_setup": temperature_setup,
        "oven_utilization": oven_utilization,
        "total_cost": total_cost,
    }


def run_greedy(scheduling_input):
    grouped_operations = group_operations_by_work_order(
        scheduling_input.operations
    )

    remaining_work_orders = list(grouped_operations.keys())

    assignment = create_deterministic_machine_assignment(
        scheduling_input.operations,
        scheduling_input.machines,
    )

    selected_order = []
    history = []

    print("\nRunning greedy scheduler...\n")

    while remaining_work_orders:
        best_candidate = None
        best_candidate_result = None
        best_candidate_order = None

        for wo in remaining_work_orders:
            candidate_order = selected_order + [wo]

            try:
                result = evaluate_work_order_order(
                    candidate_order,
                    scheduling_input,
                    grouped_operations,
                    assignment,
                )

                if best_candidate_result is None or result["fitness"] < best_candidate_result["fitness"]:
                    best_candidate = wo
                    best_candidate_result = result
                    best_candidate_order = candidate_order

            except Exception:
                continue

        if best_candidate is None:
            raise RuntimeError("Greedy scheduler could not find a feasible next work order.")

        selected_order = best_candidate_order
        remaining_work_orders.remove(best_candidate)

        history.append({
            "Step": len(selected_order),
            "SelectedWorkOrder": best_candidate,
            "Infeasible": best_candidate_result["infeasible_count"],
            "OverSoakViolations": best_candidate_result["oversoak_violations"],
            "LateOrders": best_candidate_result["late_orders"],
            "LatePenalty": best_candidate_result["late_penalty"],
            "Setup": best_candidate_result["setup"],
            "OvenUtilization": round(best_candidate_result["oven_utilization"], 2),
            "TotalCost": best_candidate_result["total_cost"],
        })

        print(
            f"Step {len(selected_order)} | "
            f"Selected: {best_candidate} | "
            f"Late: {best_candidate_result['late_orders']} | "
            f"Oven Util: {best_candidate_result['oven_utilization']:.2f}% | "
            f"Cost: {best_candidate_result['total_cost']}"
        )

    final_result = evaluate_work_order_order(
        selected_order,
        scheduling_input,
        grouped_operations,
        assignment,
    )

    individual = {
        "work_order_order": selected_order,
        "assignment": assignment,
    }

    return individual, final_result, history