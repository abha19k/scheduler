# main_ga.py

from pathlib import Path
import pandas as pd

from data_loader import load_scheduling_input
from genetic_algorithm import run_ga
from kpi import (
    build_schedule_dataframe,
    build_kpi_dataframe,
    build_machine_kpis,
)
from gantt import create_gantt_chart


DATA_FILE = Path("data/orders.xlsx")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    print("\n========================================")
    print("GA APS SCHEDULER")
    print("========================================")

    scheduling_input = load_scheduling_input(DATA_FILE)

    best_individual, result, history = run_ga(scheduling_input)

    schedule_df = build_schedule_dataframe(result["scheduled_ops"])
    oversoak_df = schedule_df[
    schedule_df["OverSoakViolation"] == True
    ].copy()
    
    if not oversoak_df.empty:
        print("\n=== OVERSOAK VIOLATIONS ===")
        print(
            oversoak_df[
                [
                    "WorkOrderID",
                    "OperationID",
                    "SequenceNumber",
                    "OperationType",
                    "AssignedMachine",
                    "ProductionEnd",
                    "OverSoakMinutes",
                    "Late",
                ]
            ]
        )
        
    kpi_df = build_kpi_dataframe(result)
    machine_kpi_df = build_machine_kpis(result["machines"])
    history_df = pd.DataFrame(history)

    excel_path = OUTPUT_DIR / "ga_aps_solution.xlsx"
    gantt_path = OUTPUT_DIR / "ga_aps_gantt.png"

    with pd.ExcelWriter(excel_path) as writer:
        kpi_df.to_excel(writer, sheet_name="KPIs", index=False)
        machine_kpi_df.to_excel(writer, sheet_name="Machine KPIs", index=False)
        schedule_df.to_excel(writer, sheet_name="Schedule", index=False)
        history_df.to_excel(writer, sheet_name="GA History", index=False)
        oversoak_df.to_excel(writer, sheet_name="OverSoak Violations", index=False)

    create_gantt_chart(
        schedule_df,
        result["machines"],
        gantt_path,
    )

    print("\n=== GA KPIs ===")
    print(kpi_df.T)

    print("\n=== GA WORK ORDER SEQUENCE ===")
    print(best_individual["work_order_order"])

    print("\n=== GA MACHINE ASSIGNMENT SAMPLE ===")
    for i, (operation_id, machine_id) in enumerate(best_individual["assignment"].items()):
        if i >= 20:
            print("...")
            break
        print(f"{operation_id} -> {machine_id}")

    if result["infeasible_count"] == 0:
        print("\nSchedule is FEASIBLE")
    else:
        print("\nSchedule is INFEASIBLE")

    print(f"OverSoak Violations: {result['oversoak_violations']}")
    print(f"Late Operations: {result['late_orders']}")
    print(f"Oven Utilization: {round(result['oven_utilization'], 2)}%")
    print(f"Total Cost: {round(result['total_cost'], 2)}")

    print(f"\nExcel exported: {excel_path}")
    print(f"Gantt exported: {gantt_path}")


if __name__ == "__main__":
    main()