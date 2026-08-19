import pandas as pd


def calculate_delivery_kpis(
    scheduled_ops
) -> dict:
    work_orders = {}

    for op in scheduled_ops:
        work_orders.setdefault(
            op.WorkOrderID,
            []
        ).append(op)

    total_work_orders = len(
        work_orders
    )

    late_work_orders = 0

    late_operations = sum(
        1
        for op in scheduled_ops
        if op.Late
    )

    for operations in work_orders.values():
        final_operation = max(
            operations,
            key=lambda op:
                op.SequenceNumber
        )

        due_end = (
            final_operation.DueDate +
            pd.Timedelta(days=1)
        )

        if (
            final_operation.EndTime is None
            or final_operation.EndTime >
            due_end
        ):
            late_work_orders += 1

    on_time_work_orders = (
        total_work_orders -
        late_work_orders
    )

    delivery_performance = (
        (
            on_time_work_orders /
            total_work_orders
        ) * 100
        if total_work_orders > 0
        else 0
    )

    return {
        "TotalWorkOrders":
            total_work_orders,

        "LateWorkOrders":
            late_work_orders,

        "TotalOperations":
            len(scheduled_ops),

        "LateOperations":
            late_operations,

        "DeliveryPerformancePercent":
            round(
                delivery_performance,
                2
            ),
    }