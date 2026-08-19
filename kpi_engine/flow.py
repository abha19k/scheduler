def calculate_makespan_hours(
    scheduled_ops
) -> float:
    start_times = [
        op.StartTime
        for op in scheduled_ops
        if op.StartTime is not None
    ]

    end_times = [
        op.EndTime
        for op in scheduled_ops
        if op.EndTime is not None
    ]

    if (
        not start_times
        or not end_times
    ):
        return 0.0

    return (
        max(end_times) -
        min(start_times)
    ).total_seconds() / 3600


def calculate_waiting_kpis(
    scheduled_ops
) -> dict:
    work_orders = {}

    for op in scheduled_ops:
        work_orders.setdefault(
            op.WorkOrderID,
            []
        ).append(op)

    waiting_hours = []

    for operations in work_orders.values():
        ordered_operations = sorted(
            operations,
            key=lambda op:
                op.SequenceNumber
        )

        for index in range(
            1,
            len(ordered_operations)
        ):
            previous_operation = (
                ordered_operations[
                    index - 1
                ]
            )

            current_operation = (
                ordered_operations[
                    index
                ]
            )

            if (
                previous_operation.EndTime
                is None
                or current_operation.StartTime
                is None
            ):
                continue

            wait_hours = (
                current_operation.StartTime
                - previous_operation.EndTime
            ).total_seconds() / 3600

            waiting_hours.append(
                max(
                    0.0,
                    wait_hours
                )
            )

    total_waiting_hours = sum(
        waiting_hours
    )

    average_waiting_hours = (
        total_waiting_hours /
        len(waiting_hours)
        if waiting_hours
        else 0.0
    )

    maximum_waiting_hours = (
        max(waiting_hours)
        if waiting_hours
        else 0.0
    )

    return {
        "TotalWaitingHours":
            round(
                total_waiting_hours,
                2
            ),

        "AverageWaitingHours":
            round(
                average_waiting_hours,
                2
            ),

        "MaximumWaitingHours":
            round(
                maximum_waiting_hours,
                2
            ),
    }


def calculate_schedule_kpis(
    scheduled_ops
) -> dict:
    makespan_hours = (
        calculate_makespan_hours(
            scheduled_ops
        )
    )

    production_hours = sum(
        op.DurationHours
        for op in scheduled_ops
    )

    waiting_kpis = (
    calculate_waiting_kpis(
        scheduled_ops
    )
)

    return {
        "MakespanHours":
            round(
                makespan_hours,
                2
            ),

        # Compatibility with existing API.
        "TotalScheduleHours":
            round(
                makespan_hours,
                2
            ),

        "ProductionHours":
            round(
                production_hours,
                2
            ),
        
         **waiting_kpis,

    }