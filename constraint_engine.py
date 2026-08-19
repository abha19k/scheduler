from constraints import machine_can_process

class ConstraintEngine:
    def machine_can_process(self, operation, machine):
        return machine_can_process(operation, machine)

    def is_heating_operation(self, operation):
        operation_type = (getattr(operation, "OperationType", None) or "").lower()
        return "heat" in operation_type or "oven" in operation_type or "batch" in operation_type

    def compatible_for_campaign(self, candidate, seed):
        if candidate is None or not self.is_heating_operation(candidate):
            return False
        return (
            candidate.ProductFamily == seed.ProductFamily
            and candidate.Temperature == seed.Temperature
        )

    def batch_capacity_ok(self, operations, machine):
        operations = list(operations)
        total_weight = sum(float(getattr(op, "Weight", 0) or 0) for op in operations)
        total_length = sum(float(getattr(op, "Length", 0) or 0) for op in operations)
        if machine.MaxWeight is not None and total_weight > machine.MaxWeight:
            return False
        if machine.MaxLength is not None and total_length > machine.MaxLength:
            return False
        return True

    def work_order_can_use_oven_for_all_heating(self, work_order_id, operations_by_wo, oven):
        for op in operations_by_wo[work_order_id].values():
            if self.is_heating_operation(op) and not self.machine_can_process(op, oven):
                return False
        return True
