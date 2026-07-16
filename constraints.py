# constraints.py

def machine_can_process(operation, machine):
    if machine.Status.lower() != "active":
        return False

    if machine.MachineID not in operation.AllowedMachines:
        return False

    if machine.MaxWeight is not None and operation.Weight is not None:
        if operation.Weight > machine.MaxWeight:
            return False

    if machine.MaxLength is not None and operation.Length is not None:
        if operation.Length > machine.MaxLength:
            return False

    if machine.MaxTemperature is not None and operation.Temperature is not None:
        if operation.Temperature > machine.MaxTemperature:
            return False

    return True