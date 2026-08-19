from datetime import datetime, timedelta
from calendar_utils import adjust_to_calendar

class TimelineManager:
    def __init__(self, machines, calendar_details):
        self.machines = machines
        self.calendar_details = calendar_details

    @staticmethod
    def item_start(item):
        return item.get("SetupStart") or item.get("StartTime")

    def timeline(self, machine_id):
        machine = self.machines[machine_id]
        return sorted(
            [
                item for item in (getattr(machine, "Timeline", []) or [])
                if self.item_start(item) is not None and item.get("EndTime") is not None
            ],
            key=self.item_start,
        )

    def clear_non_fixed(self):
        for machine in self.machines.values():
            machine.Timeline = [
                item for item in (getattr(machine, "Timeline", []) or [])
                if item.get("IsFixed") or item.get("IsManual")
            ]

    def previous_operation(self, machine_id, before_time=None):
        items = self.timeline(machine_id)
        if before_time is not None:
            items = [x for x in items if x["EndTime"] <= before_time]
        if not items:
            return None
        return max(items, key=lambda x: x["EndTime"]).get("Operation")

    def reserve(self, machine_id, item, validate_overlap=True):
        start = self.item_start(item)
        end = item.get("EndTime")
        if start is None or end is None:
            raise ValueError("Timeline reservation requires start and end")
        if validate_overlap and self.overlaps(machine_id, start, end):
            raise ValueError(f"Timeline overlap on {machine_id}: {start} -> {end}")
        machine = self.machines[machine_id]
        machine.Timeline.append(item)
        machine.Timeline.sort(key=lambda x: self.item_start(x) or x["StartTime"])

    def overlaps(self, machine_id, start, end, ignore_item=None):
        for item in self.timeline(machine_id):
            if ignore_item is not None and item is ignore_item:
                continue
            existing_start = self.item_start(item)
            existing_end = item["EndTime"]
            if start < existing_end and end > existing_start:
                return True
        return False

    def available_time(self, machine_id, planning_start):
        items = self.timeline(machine_id)
        machine = self.machines[machine_id]
        if not items:
            return getattr(machine, "StartTime", None) or planning_start
        return max(x["EndTime"] for x in items)

    def validate_machine(self, machine_id):
        items = self.timeline(machine_id)
        for previous, current in zip(items, items[1:]):
            if self.item_start(current) < previous["EndTime"]:
                raise ValueError(f"Timeline overlap on {machine_id}")

    def validate_all(self):
        for machine_id in self.machines:
            self.validate_machine(machine_id)
