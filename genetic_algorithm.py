# genetic_algorithm.py

import random
from copy import deepcopy
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

from constraints import machine_can_process
from machine_engine import schedule_operations


# =========================================================
# GROUP OPERATIONS BY WORK ORDER
# =========================================================

def group_operations_by_work_order(operations):
    grouped = {}

    for op in operations:
        grouped.setdefault(op.WorkOrderID, []).append(op)

    for work_order_id in grouped:
        grouped[work_order_id].sort(key=lambda x: x.SequenceNumber)

    return grouped


def expand_work_order_order(work_order_order, grouped_operations):
    expanded = []

    max_sequence = max(
        op.SequenceNumber
        for ops in grouped_operations.values()
        for op in ops
    )

    for sequence_number in range(1, max_sequence + 1):
        for work_order_id in work_order_order:
            for op in grouped_operations[work_order_id]:
                if op.SequenceNumber == sequence_number:
                    expanded.append(op)

    return expanded



def is_heating_operation(op):
    operation_type = (op.OperationType or "").lower()

    return (
        "heat" in operation_type
        or "oven" in operation_type
        or "batch" in operation_type
    )


def is_press_operation(op):
    operation_type = (op.OperationType or "").lower()
    return "press" in operation_type


# =========================================================
# MACHINE ASSIGNMENT
# =========================================================

def create_machine_assignment(operations, machines):
    assignment = {}

    machine_load = {
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

        min_load = min(machine_load[m] for m in feasible)

        least_loaded = [
            m for m in feasible
            if machine_load[m] == min_load
        ]

        chosen = random.choice(least_loaded)

        assignment[op.OperationID] = chosen
        machine_load[chosen] += 1

    return assignment


def hard_lock_same_temperature_oven_assignment(operations, machines, assignment):
    grouped = {}

    for op in operations:
        if not is_heating_operation(op):
            continue

        if op.Temperature is None:
            continue

        grouped.setdefault(
            (op.WorkOrderID, op.Temperature),
            []
        ).append(op)

    for _, ops in grouped.items():
        if len(ops) <= 1:
            continue

        common_feasible_ovens = None

        for op in ops:
            feasible_ovens_for_op = set()

            for machine_id, machine in machines.items():
                if machine.MachineType.lower() != "batch":
                    continue

                if machine_id not in op.AllowedMachines:
                    continue

                if machine_can_process(op, machine):
                    feasible_ovens_for_op.add(machine_id)

            if common_feasible_ovens is None:
                common_feasible_ovens = feasible_ovens_for_op
            else:
                common_feasible_ovens &= feasible_ovens_for_op

        if not common_feasible_ovens:
            continue

        current_oven_counts = {}

        for op in ops:
            current_machine_id = assignment.get(op.OperationID)

            if current_machine_id in common_feasible_ovens:
                current_oven_counts[current_machine_id] = (
                    current_oven_counts.get(current_machine_id, 0) + 1
                )

        if current_oven_counts:
            chosen_oven = max(
                current_oven_counts,
                key=current_oven_counts.get
            )
        else:
            chosen_oven = random.choice(
                list(common_feasible_ovens)
            )

        for op in ops:
            assignment[op.OperationID] = chosen_oven

    return assignment


def create_individual(work_order_ids, operations, machines):
    work_order_order = work_order_ids.copy()
    random.shuffle(work_order_order)

    assignment = create_machine_assignment(
        operations,
        machines,
    )

    assignment = hard_lock_same_temperature_oven_assignment(
        operations,
        machines,
        assignment,
    )

    return {
        "work_order_order": work_order_order,
        "assignment": assignment,
    }


# =========================================================
# UTILIZATION
# =========================================================

def calculate_oven_utilization(machines):
    oven_total_time = 0
    oven_busy_time = 0

    for machine in machines.values():
        if machine.MachineType.lower() != "batch":
            continue

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

        total_hours = (
            machine_end - machine_start
        ).total_seconds() / 3600

        oven_total_time += total_hours

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
                continue

            _, last_end = merged[-1]

            if start <= last_end:
                merged[-1][1] = max(last_end, end)
            else:
                merged.append([start, end])

        busy_hours = sum(
            (end - start).total_seconds() / 3600
            for start, end in merged
        )

        oven_busy_time += busy_hours

    if oven_total_time == 0:
        return 0

    return (oven_busy_time / oven_total_time) * 100


# =========================================================
# PENALTY FUNCTIONS
# =========================================================

def calculate_same_temperature_oven_change_penalty(scheduled_ops):
    grouped = {}

    for op in scheduled_ops:
        if not is_heating_operation(op):
            continue

        if op.Temperature is None:
            continue

        grouped.setdefault(
            (op.WorkOrderID, op.Temperature),
            set()
        ).add(op.AssignedMachine)

    penalty = 0

    for ovens in grouped.values():
        if len(ovens) > 1:
            penalty += (len(ovens) - 1) * 500

    oven_ops = {}

    for op in scheduled_ops:
        if not is_heating_operation(op):
            continue

        oven_ops.setdefault(
            op.AssignedMachine,
            []
        ).append(op)

    for _, ops in oven_ops.items():
        ops.sort(key=lambda x: x.StartTime)

        prev_family = None

        for op in ops:
            current_family = op.ProductFamily

            if (
                prev_family is not None
                and current_family is not None
                and prev_family != current_family
            ):
                penalty += 50

            prev_family = current_family

    return penalty


def calculate_same_press_preference_penalty(scheduled_ops):
    grouped = {}

    for op in scheduled_ops:
        if not is_press_operation(op):
            continue

        grouped.setdefault(
            op.WorkOrderID,
            set()
        ).add(op.AssignedMachine)

    penalty = 0

    for presses in grouped.values():
        if len(presses) > 1:
            penalty += (len(presses) - 1) * 120

    return penalty


# =========================================================
# EVALUATION
# =========================================================

def calculate_delivery_performance(scheduled_ops):
    work_orders = {}

    for op in scheduled_ops:
        work_orders.setdefault(
            op.WorkOrderID,
            []
        ).append(op)

    if not work_orders:
        return 0

    late_work_orders = 0

    for ops in work_orders.values():
        if any(op.Late for op in ops):
            late_work_orders += 1

    total_work_orders = len(work_orders)
    on_time_work_orders = total_work_orders - late_work_orders

    return round(
        (on_time_work_orders / total_work_orders) * 100,
        2
    )


def evaluate_individual(individual, scheduling_input, grouped_operations):
    expanded_operation_order = expand_work_order_order(
        individual["work_order_order"],
        grouped_operations,
    )

    scheduled_ops, machines, infeasible_count, oversoak_violations = (
        schedule_operations(
            expanded_operation_order,
            individual["assignment"],
            scheduling_input,
        )
    )

    late_orders = sum(
        1 for op in scheduled_ops
        if op.Late
    )

    late_penalty = sum(
        op.LatePenalty
        for op in scheduled_ops
    )

    total_setup = sum(
        op.SetupMinutes
        for op in scheduled_ops
    )

    family_setup = sum(
        op.FamilySetupMinutes
        for op in scheduled_ops
    )

    width_setup = sum(
        op.WidthSetupMinutes
        for op in scheduled_ops
    )

    temperature_setup = sum(
        op.TemperatureSetupMinutes
        for op in scheduled_ops
    )

    oven_utilization = calculate_oven_utilization(
        machines
    )

    same_temperature_oven_penalty = (
        calculate_same_temperature_oven_change_penalty(
            scheduled_ops
        )
    )

    same_press_penalty = (
        calculate_same_press_preference_penalty(
            scheduled_ops
        )
    )

    hard_infeasibility_penalty = (
        infeasible_count * 10_000_000
    )

    late_priority_penalty = late_orders * 10_000_000

    oversoak_penalty = 0

    total_cost = total_setup + late_penalty



    industrial_score = (
        hard_infeasibility_penalty
        + late_priority_penalty
        + late_penalty
        + total_setup
        + same_temperature_oven_penalty
        + same_press_penalty
    )


    delivery_performance = calculate_delivery_performance(
        scheduled_ops
    )

    objective_overrides = getattr(
        scheduling_input,
        "objective_overrides",
        {}
    )

    if objective_overrides.get("PrioritizeDelivery"):
        
        fitness = (
            hard_infeasibility_penalty,
            late_orders,
            late_penalty,
            -delivery_performance,
            total_setup,
            industrial_score,
        )

    elif objective_overrides.get("PrioritizeOvenUtilization"):
        fitness = (
            hard_infeasibility_penalty,
            -oven_utilization,
            same_temperature_oven_penalty,
            late_orders,
            late_penalty,
            total_setup,
            industrial_score,
        )

    elif objective_overrides.get("PrioritizeSetupReduction"):
        fitness = (
            hard_infeasibility_penalty,
            total_setup,
            same_temperature_oven_penalty,
            same_press_penalty,
            late_orders,
            late_penalty,
            industrial_score,
        )

    elif objective_overrides.get("PrioritizeTemperatureStability"):
        fitness = (
            hard_infeasibility_penalty,
            same_temperature_oven_penalty,
            -oven_utilization,
            total_setup,
            late_orders,
            late_penalty,
            industrial_score,
        )

    else:
        fitness = (
            hard_infeasibility_penalty,

            late_orders,
            late_penalty,

            -delivery_performance,

            -oven_utilization,

            total_setup,

            same_temperature_oven_penalty,
            same_press_penalty,

            industrial_score
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

        "same_temperature_oven_penalty":
            same_temperature_oven_penalty,

        "same_press_penalty":
            same_press_penalty,

        "delivery_performance":
            delivery_performance,

        "industrial_score":
            industrial_score,

        "total_cost":
            total_cost,
    }



def is_feasible_result(result):
    return (
        result["infeasible_count"] == 0
    )


# =========================================================
# GA OPERATORS
# =========================================================

def selection(evaluated, tournament_size):
    candidates = random.sample(
        evaluated,
        min(
            tournament_size,
            len(evaluated)
        )
    )

    candidates.sort(
        key=lambda x: x["result"]["fitness"]
    )

    return candidates[0]["individual"]


def crossover(parent1, parent2):
    p1_order = parent1["work_order_order"]
    p2_order = parent2["work_order_order"]

    size = len(p1_order)

    if size < 2:
        return deepcopy(parent1)

    start, end = sorted(
        random.sample(
            range(size),
            2
        )
    )

    child_order = [None] * size
    child_order[start:end] = p1_order[start:end]

    remaining = [
        wo for wo in p2_order
        if wo not in child_order
    ]

    ptr = 0

    for i in range(size):
        if child_order[i] is None:
            child_order[i] = remaining[ptr]
            ptr += 1

    child_assignment = {}

    operation_ids = (
        set(parent1["assignment"].keys())
        | set(parent2["assignment"].keys())
    )

    for operation_id in operation_ids:
        chosen = (
            parent1["assignment"].get(operation_id)
            if random.random() < 0.5
            else parent2["assignment"].get(operation_id)
        )

        if chosen is None:
            chosen = (
                parent1["assignment"].get(operation_id)
                or parent2["assignment"].get(operation_id)
            )

        child_assignment[operation_id] = chosen

    return {
        "work_order_order": child_order,
        "assignment": child_assignment,
    }


def mutate(individual, scheduling_input, mutation_rate):
    individual = deepcopy(individual)

    if random.random() >= mutation_rate:
        return individual

    mutation_type = random.choice([
        "swap_work_orders",
        "reverse_work_orders",
        "scramble_work_orders",
        "machine_change",
    ])

    work_order_order = individual["work_order_order"]

    if (
        mutation_type == "swap_work_orders"
        and len(work_order_order) >= 2
    ):
        i, j = random.sample(
            range(len(work_order_order)),
            2
        )

        (
            work_order_order[i],
            work_order_order[j]
        ) = (
            work_order_order[j],
            work_order_order[i]
        )

    elif (
        mutation_type == "reverse_work_orders"
        and len(work_order_order) >= 2
    ):
        i, j = sorted(
            random.sample(
                range(len(work_order_order)),
                2
            )
        )

        work_order_order[i:j] = list(
            reversed(
                work_order_order[i:j]
            )
        )

    elif (
        mutation_type == "scramble_work_orders"
        and len(work_order_order) >= 2
    ):
        i, j = sorted(
            random.sample(
                range(len(work_order_order)),
                2
            )
        )

        subset = work_order_order[i:j]
        random.shuffle(subset)
        work_order_order[i:j] = subset

    elif mutation_type == "machine_change":
        op = random.choice(
            scheduling_input.operations
        )

        feasible = [
            machine_id
            for machine_id, machine in scheduling_input.machines.items()
            if machine_can_process(op, machine)
        ]

        if feasible:
            individual["assignment"][op.OperationID] = (
                random.choice(feasible)
            )

            individual["assignment"] = (
                hard_lock_same_temperature_oven_assignment(
                    scheduling_input.operations,
                    scheduling_input.machines,
                    individual["assignment"],
                )
            )

    return individual


# =========================================================
# POPULATION
# =========================================================

def create_smart_population(
    work_order_ids,
    operations,
    machines,
    population_size
):
    population = []
    grouped = group_operations_by_work_order(
        operations
    )

    due_seed = sorted(
        work_order_ids,
        key=lambda wo: min(
            op.DueDate
            for op in grouped[wo]
        )
    )

    family_seed = sorted(
        work_order_ids,
        key=lambda wo: (
            grouped[wo][0].ProductFamily or "",
            min(op.DueDate for op in grouped[wo])
        )
    )

    reverse_due_seed = list(
        reversed(due_seed)
    )

    original_feasible_seed = sorted(
        work_order_ids,
        key=lambda wo: (
            min(op.DueDate for op in grouped[wo]),
            wo
        )
    )

    for seed in [
        due_seed,
        family_seed,
        reverse_due_seed,
        original_feasible_seed,
    ]:
        assignment = create_machine_assignment(
            operations,
            machines
        )

        assignment = hard_lock_same_temperature_oven_assignment(
            operations,
            machines,
            assignment,
        )

        population.append({
            "work_order_order": seed,
            "assignment": assignment,
        })

    while len(population) < population_size:
        population.append(
            create_individual(
                work_order_ids,
                operations,
                machines,
            )
        )

    return population


# =========================================================
# GA HISTORY CHART EXPORT
# =========================================================

def export_ga_history_charts(history, scenario_id="BASE"):
    if not history:
        return

    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    safe_scenario_id = str(scenario_id).lower()

    history_df = pd.DataFrame(history)

    history_df.to_csv(
        output_dir / f"{safe_scenario_id}_ga_generation_history.csv",
        index=False
    )

    chart_specs = [
        (
            "BestExportOvenUtilization",
            "Oven Utilization (%)",
            "Oven Utilization Improvement Over Generations",
            f"{safe_scenario_id}_oven_utilization_over_generations.png",
        ),
        (
            "BestExportSetup",
            "Setup Minutes",
            "Setup Reduction Over Generations",
            f"{safe_scenario_id}_setup_over_generations.png",
        ),
        (
            "BestExportIndustrialScore",
            "Industrial Score",
            "Industrial Score Improvement Over Generations",
            f"{safe_scenario_id}_industrial_score_over_generations.png",
        ),
        (
            "BestExportTotalCost",
            "Total Cost",
            "Total Cost Reduction Over Generations",
            f"{safe_scenario_id}_total_cost_over_generations.png",
        ),
        (
            "BestExportDeliveryPerformance",
            "Delivery Performance (%)",
            "Delivery Performance Over Generations",
            f"{safe_scenario_id}_delivery_performance_over_generations.png",
        ),
    ]

    for column, ylabel, title, filename in chart_specs:
        if column not in history_df.columns:
            continue

        plt.figure(
            figsize=(10, 5)
        )

        plt.plot(
            history_df["Generation"],
            history_df[column],
            marker="o"
        )

        plt.xlabel("Generation")
        plt.ylabel(ylabel)
        plt.title(title)

        if "DeliveryPerformance" in column:
            plt.ylim(0, 105)

        plt.grid(True)
        plt.tight_layout()

        plt.savefig(
            output_dir / filename,
            dpi=300
        )

        plt.close()

    required_columns = [
        "BestExportSetup",
        "BestExportTotalCost",
        "BestExportIndustrialScore",
    ]

    if all(
        column in history_df.columns
        for column in required_columns
    ):
        plt.figure(
            figsize=(10, 5)
        )

        plt.plot(
            history_df["Generation"],
            history_df["BestExportSetup"],
            marker="o",
            label="Setup"
        )

        plt.plot(
            history_df["Generation"],
            history_df["BestExportTotalCost"],
            marker="o",
            label="Total Cost"
        )

        plt.plot(
            history_df["Generation"],
            history_df["BestExportIndustrialScore"],
            marker="o",
            label="Industrial Score"
        )

        plt.xlabel("Generation")
        plt.ylabel("Value")
        plt.title("GA Improvement Over Generations")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()

        plt.savefig(
            output_dir / f"{safe_scenario_id}_ga_cost_comparison_over_generations.png",
            dpi=300
        )

        plt.close()


# =========================================================
# RUN GA
# =========================================================

def run_ga(scheduling_input):
    params = scheduling_input.parameters

    scenario_id = getattr(
        scheduling_input,
        "active_scenario_id",
        "BASE"
    )

    scenario_name = scenario_id

    if (
        hasattr(scheduling_input, "scenario_definitions")
        and scenario_id in scheduling_input.scenario_definitions
    ):
        scenario_name = (
            scheduling_input
            .scenario_definitions[scenario_id]
            .ScenarioName
        )

    print("\n========================================")
    print(f"ACTIVE SCENARIO: {scenario_name}")
    print("========================================")
    print(
        f"Parameters | "
        f"Population={params.PopulationSize}, "
        f"Generations={params.Generations}, "
        f"MutationRate={params.MutationRate}, "
        f"LatePenalty={params.LateOrderPenalty}, "
        f"MaxOverSoak={params.MaxOverSoakMinutes}"
    )

    grouped_operations = group_operations_by_work_order(
        scheduling_input.operations
    )

    work_order_ids = list(
        grouped_operations.keys()
    )

    print("\n========================================")
    print("GA CHROMOSOME DESIGN")
    print("========================================")
    print(f"Unique work orders: {len(work_order_ids)}")
    print(f"Total operations: {len(scheduling_input.operations)}")
    print("Permuting work orders only, not operations.")

    population = create_smart_population(
        work_order_ids=work_order_ids,
        operations=scheduling_input.operations,
        machines=scheduling_input.machines,
        population_size=params.PopulationSize,
    )

    best_individual = None
    best_result = None

    best_feasible_individual = None
    best_feasible_result = None

    history = []

    print_every = int(
        getattr(
            params,
            "PrintEvery",
            1
        )
    )

    early_stop_generations = int(
        getattr(
            params,
            "EarlyStopGenerations",
            200
        )
    )

    no_improvement_count = 0

    print(
        "\nRunning WorkOrder-level Industrial APS Genetic Algorithm...\n"
    )

    for generation in range(params.Generations):
        evaluated = []
        improved_this_generation = False

        for individual in population:
            try:
                result = evaluate_individual(
                    individual,
                    scheduling_input,
                    grouped_operations,
                )

                evaluated.append({
                    "individual": individual,
                    "result": result,
                })

                if (
                    best_result is None
                    or result["fitness"] < best_result["fitness"]
                ):
                    best_result = result
                    best_individual = individual
                    improved_this_generation = True

                if is_feasible_result(result):
                    if (
                        best_feasible_result is None
                        or result["fitness"] < best_feasible_result["fitness"]
                    ):
                        best_feasible_result = result
                        best_feasible_individual = individual
                        improved_this_generation = True

            except Exception as e:
                print("\n================================")
                print("EVALUATION FAILED")
                print(type(e).__name__)
                print(str(e))
                print("================================\n")
                raise


        if not evaluated:
            raise RuntimeError(
                "No feasible schedules found in this generation."
            )

        evaluated.sort(
            key=lambda x: x["result"]["fitness"]
        )

        if improved_this_generation:
            no_improvement_count = 0
        else:
            no_improvement_count += 1

        current_export_result = (
            best_feasible_result
            if best_feasible_result is not None
            else best_result
        )

        history.append({
            "Generation": generation + 1,

            "BestOverallInfeasible":
                best_result["infeasible_count"],

            "BestOverallOverSoak":
                best_result["oversoak_violations"],

            "BestOverallLate":
                best_result["late_orders"],

            "BestOverallDeliveryPerformance":
                best_result["delivery_performance"],

            "BestOverallSetup":
                best_result["setup"],

            "BestOverallTotalCost":
                best_result["total_cost"],

            "BestOverallIndustrialScore":
                best_result["industrial_score"],

            "BestOverallOvenUtilization":
                round(best_result["oven_utilization"], 2),

            "BestOverallSameTempOvenPenalty":
                best_result["same_temperature_oven_penalty"],

            "BestOverallSamePressPenalty":
                best_result["same_press_penalty"],

            "BestFeasibleFound":
                best_feasible_result is not None,

            "BestExportInfeasible":
                current_export_result["infeasible_count"],

            "BestExportOverSoak":
                current_export_result["oversoak_violations"],

            "BestExportLate":
                current_export_result["late_orders"],

            "BestExportDeliveryPerformance":
                current_export_result["delivery_performance"],

            "BestExportSetup":
                current_export_result["setup"],

            "BestExportTotalCost":
                current_export_result["total_cost"],

            "BestExportIndustrialScore":
                current_export_result["industrial_score"],

            "BestExportOvenUtilization":
                round(
                    current_export_result["oven_utilization"],
                    2
                ),

            "BestExportSameTempOvenPenalty":
                current_export_result[
                    "same_temperature_oven_penalty"
                ],

            "BestExportSamePressPenalty":
                current_export_result[
                    "same_press_penalty"
                ],
        })

        if (
            generation % print_every == 0
            or generation == params.Generations - 1
        ):
            print(
                f"Generation {generation + 1} | "
                f"Infeasible: {best_result['infeasible_count']} | "
                f"OverSoak: {best_result['oversoak_violations']} | "
                f"Late: {best_result['late_orders']} | "
                f"Delivery: {best_result['delivery_performance']}% | "
                f"Oven Util: {best_result['oven_utilization']:.2f}% | "
                f"Setup: {best_result['setup']} | "
                f"Cost: {best_result['total_cost']} | "
                f"Industrial Score: {best_result['industrial_score']} | "
                f"Export Feasible: {best_feasible_result is not None}"
            )

            if best_feasible_result is not None:
                print(
                    f"    Best feasible | "
                    f"Late: {best_feasible_result['late_orders']} | "
                    f"Delivery: {best_feasible_result['delivery_performance']}% | "
                    f"Oven Util: {best_feasible_result['oven_utilization']:.2f}% | "
                    f"Setup: {best_feasible_result['setup']} | "
                    f"Cost: {best_feasible_result['total_cost']} | "
                    f"Industrial Score: "
                    f"{best_feasible_result['industrial_score']}"
                )

        if no_improvement_count >= early_stop_generations:
            print(
                f"\nEarly stopping: no improvement for "
                f"{early_stop_generations} generations."
            )
            break

        elite_size = min(
            params.EliteSize,
            len(evaluated)
        )

        new_population = [
            evaluated[i]["individual"]
            for i in range(elite_size)
        ]

        while len(new_population) < params.PopulationSize:
            p1 = selection(
                evaluated,
                params.TournamentSize
            )

            p2 = selection(
                evaluated,
                params.TournamentSize
            )

            child = crossover(
                p1,
                p2
            )

            child["assignment"] = hard_lock_same_temperature_oven_assignment(
                scheduling_input.operations,
                scheduling_input.machines,
                child["assignment"],
            )

            child = mutate(
                child,
                scheduling_input,
                params.MutationRate
            )

            new_population.append(
                child
            )

        population = new_population

    if best_feasible_individual is not None:
        print("\nExporting BEST FEASIBLE schedule.")
        final_individual = best_feasible_individual
    else:
        print(
            "\nWARNING: No feasible schedule found. "
            "Exporting best overall schedule."
        )
        final_individual = best_individual

    final_result = evaluate_individual(
        final_individual,
        scheduling_input,
        grouped_operations,
    )

    export_ga_history_charts(
        history,
        scenario_id=scenario_id,
    )

    return final_individual, final_result, history