# gantt.py
import matplotlib
matplotlib.use("Agg")

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch


# =========================================================
# COLOR MAP
# =========================================================

PRODUCT_COLORS = {
    "A": "gold",
    "B": "limegreen",
    # "C": "cyan",
    # "D": "orange",
    # "E": "violet",
    # "F": "red",
}


# =========================================================
# GANTT
# =========================================================

def create_gantt_chart(
    schedule_df,
    machines,
    output_path
):

    output_path = Path(output_path)

    fig_height = max(6, len(machines) * 1.2)

    fig, ax = plt.subplots(
        figsize=(22, fig_height)
    )

    planning_start = min(
        schedule_df["SetupStart"]
    )

    machine_ids = sorted(
        schedule_df["AssignedMachine"].unique()
    )

    machine_positions = {
        machine_id: i
        for i, machine_id
        in enumerate(machine_ids)
    }

    # =====================================================
    # DRAW OPERATIONS
    # =====================================================

    for _, row in schedule_df.iterrows():

        machine_id = row["AssignedMachine"]

        y = machine_positions[machine_id]

        # =================================================
        # SETUP BLOCK
        # =================================================

        setup_minutes = row["TotalSetupMinutes"]

        if setup_minutes > 0:

            setup_start_hours = (
                (
                    row["SetupStart"] -
                    planning_start
                ).total_seconds() / 3600
            )

            setup_duration_hours = (
                setup_minutes / 60
            )

            ax.barh(
                y=y,

                width=setup_duration_hours,

                left=setup_start_hours,

                height=0.6,

                color="lightgrey",

                edgecolor="black",

                hatch="//",

                alpha=0.9,
            )

        # =================================================
        # PRODUCTION BLOCK
        # =================================================

        production_start_hours = (
            (
                row["ProductionStart"] -
                planning_start
            ).total_seconds() / 3600
        )

        production_duration_hours = (
            (
                row["ProductionEnd"] -
                row["ProductionStart"]
            ).total_seconds() / 3600
        )

        product_family = row["ProductFamily"]

        bar_color = PRODUCT_COLORS.get(
            product_family,
            "skyblue"
        )

        ax.barh(
            y=y,

            width=production_duration_hours,

            left=production_start_hours,

            height=0.6,

            color=bar_color,

            edgecolor="black",
        )

        # =================================================
        # LABEL
        # =================================================

        label = (
            f'{row["WorkOrderID"]}\n'
            f'{row["OperationID"]}\n'
            f'PF:{row["ProductFamily"]}'
        )

        ax.text(
            production_start_hours +
            production_duration_hours / 2,

            y,

            label,

            ha="center",
            va="center",

            fontsize=7,

            color="black",
        )

        # =================================================
        # LATE LABEL
        # =================================================

        if row["Late"]:

            ax.text(
                production_start_hours +
                production_duration_hours / 2,

                y + 0.28,

                "LATE",

                color="red",

                fontsize=7,

                ha="center",

                fontweight="bold",
            )

        # =================================================
        # OVERSOAK LABEL
        # =================================================

        if row["OverSoakViolation"]:

            ax.text(
                production_start_hours +
                production_duration_hours / 2,

                y - 0.32,

                "OVERSOAK",

                color="darkred",

                fontsize=7,

                ha="center",

                fontweight="bold",
            )

    # =====================================================
    # AXIS
    # =====================================================

    ax.set_yticks(
        list(machine_positions.values())
    )

    ax.set_yticklabels(
        list(machine_positions.keys())
    )

    ax.set_xlabel(
        "Hours from Planning Start"
    )

    ax.set_ylabel(
        "Machines"
    )

    ax.set_title(
        "Industrial APS Schedule"
    )

    ax.grid(
        axis="x",
        linestyle="--",
        alpha=0.4
    )

    # =====================================================
    # LEGEND
    # =====================================================

    legend_items = [

        Patch(
            facecolor="lightgrey",
            edgecolor="black",
            hatch="//",
            label="Setup"
        )
    ]

    for pf, color in PRODUCT_COLORS.items():

        legend_items.append(

            Patch(
                facecolor=color,
                edgecolor="black",
                label=f"ProductFamily {pf}"
            )
        )

    ax.legend(
        handles=legend_items,
        loc="upper right"
    )

    plt.tight_layout()

    plt.savefig(
        output_path,
        dpi=150
    )

    plt.close()

    return output_path