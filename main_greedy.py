# main_greedy.py

from pathlib import Path
import pandas as pd

from data_loader import load_scheduling_input
from greedy_algorithm import run_greedy
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
    print("GREEDY APS SCHEDULER")
    print("========================================")

    scheduling_input = load_scheduling_input(DATA_FILE)

    best_individual, result, history = run_greedy(scheduling_input)

    schedule_df = build_schedule_dataframe(result["scheduled_ops"])
    kpi_df = build_kpi_dataframe(result)
    machine_kpi_df = build_machine_kpis(result["machines"])
    history_df = pd.DataFrame(history)

    excel_path = OUTPUT_DIR / "greedy_aps_solution.xlsx"
    gantt_path = OUTPUT_DIR / "greedy_aps_gantt.png"

    with pd.ExcelWriter(excel_path) as writer:
        kpi_df.to_excel(writer, sheet_name="KPIs", index=False)
        machine_kpi_df.to_excel(writer, sheet_name="Machine KPIs", index=False)
        schedule_df.to_excel(writer, sheet_name="Schedule", index=False)
        history_df.to_excel(writer, sheet_name="Greedy History", index=False)

    create_gantt_chart(
        schedule_df,
        result["machines"],
        gantt_path,
    )

    print("\n=== GREEDY KPIs ===")
    print(kpi_df.T)

    print("\n=== GREEDY WORK ORDER SEQUENCE ===")
    print(best_individual["work_order_order"])

    print(f"\nExcel exported: {excel_path}")
    print(f"Gantt exported: {gantt_path}")


if __name__ == "__main__":
    main()