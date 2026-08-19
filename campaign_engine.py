from models import Campaign

class CampaignBuilder:
    def __init__(self, machines, machine_assignment, constraint_engine):
        self.machines = machines
        self.machine_assignment = machine_assignment
        self.constraints = constraint_engine

    def _candidate_ovens(self, operation):
        result = []
        for machine_id, machine in self.machines.items():
            if (machine.MachineType or "").lower() == "regular":
                continue
            if self.constraints.machine_can_process(operation, machine):
                result.append(machine_id)
        return sorted(result)

    def build(self, work_order_order, operations_by_wo):
        remaining = [str(x) for x in work_order_order]
        campaigns = []
        counter = 1

        # ---------------------------------------------------------
        # PROJECTED OVEN LOAD
        #
        # Used while building campaigns so we do not keep assigning
        # every campaign to the same one or two ovens.
        # ---------------------------------------------------------

        planned_oven_load_hours = {
            machine_id: 0.0
            for machine_id, machine in self.machines.items()
            if (machine.MachineType or "").lower() != "regular"
        }

        planned_campaign_count = {
            machine_id: 0
            for machine_id in planned_oven_load_hours
        }

        while remaining:
            seed_wo = remaining[0]
            seed_op = operations_by_wo[seed_wo].get(1)

            if seed_op is None:
                raise ValueError(f"Missing sequence 1 for work order {seed_wo}")
            if not self.constraints.is_heating_operation(seed_op):
                raise ValueError(f"Sequence 1 must be heating for work order {seed_wo}")

            best = None

            for oven_id in self._candidate_ovens(seed_op):
                oven = self.machines[oven_id]
                batch_wos = []
                batch_ops = []

                for wo in remaining:
                    candidate_op = operations_by_wo[wo].get(1)
                    if not self.constraints.compatible_for_campaign(candidate_op, seed_op):
                        continue
                    if not self.constraints.work_order_can_use_oven_for_all_heating(
                        wo, operations_by_wo, oven
                    ):
                        continue

                    trial = batch_ops + [candidate_op]
                    if not self.constraints.batch_capacity_ok(trial, oven):
                        continue

                    batch_wos.append(wo)
                    batch_ops.append(candidate_op)

                    campaign_heating_hours = 0.0

                    heating_sequences = set()

                    for wo in batch_wos:
                        for seq, op in operations_by_wo[wo].items():
                            if self.constraints.is_heating_operation(op):
                                heating_sequences.add(seq)

                    for seq in heating_sequences:
                        sequence_ops = [
                            operations_by_wo[wo].get(seq)
                            for wo in batch_wos
                        ]

                        sequence_ops = [
                            op
                            for op in sequence_ops
                            if (
                                op is not None
                                and self.constraints.is_heating_operation(op)
                            )
                        ]

                        if sequence_ops:
                            # These WOs heat together, therefore use batch duration,
                            # not the sum of each WO duration.
                            campaign_heating_hours += max(
                                float(op.DurationHours)
                                for op in sequence_ops
                            )

                if seed_wo not in batch_wos:
                    continue

                mismatches = sum(
                    1 for op in batch_ops
                    if self.machine_assignment.get(op.OperationID) not in (None, oven_id)
                )

                preferred = self.machine_assignment.get(seed_op.OperationID)
                seed_penalty = 0 if preferred in (None, oven_id) else 1


                score = (
                    # First create the best / fullest valid batch.
                    -len(batch_wos),

                    # Respect the GA assignment where possible.
                    seed_penalty,

                    # Then spread campaigns across available ovens.
                    round(
                        planned_oven_load_hours.get(
                            oven_id,
                            0.0,
                        ),
                        4,
                    ),

                    planned_campaign_count.get(
                        oven_id,
                        0,
                    ),

                    # Operation-level GA disagreement comes later.
                    mismatches,

                    oven_id,
                )

                if best is None or score < best[0]:
                    best = (
                        score,
                        oven_id,
                        tuple(batch_wos),
                        campaign_heating_hours,
                    )

            if best is None:
                raise ValueError(f"Could not create campaign for {seed_wo}")

            (
                _,
                preferred_oven_id,
                members,
                campaign_heating_hours,
            ) = best

            campaigns.append(Campaign(
                campaign_id=f"BATCH_{counter}",
                persistent_batch_id=f"PBATCH_{counter}",
                work_order_ids=members,
                preferred_oven_id=preferred_oven_id,
            ))

            counter += 1

            planned_oven_load_hours[
                preferred_oven_id
            ] += campaign_heating_hours

            planned_campaign_count[
                preferred_oven_id
            ] += 1


            member_set = set(members)
            remaining = [wo for wo in remaining if wo not in member_set]

        self.validate(campaigns, work_order_order)
        return campaigns

    @staticmethod
    def validate(campaigns, expected_work_orders):
        seen = set()
        for campaign in campaigns:
            members = set(campaign.work_order_ids)
            duplicates = seen & members
            if duplicates:
                raise RuntimeError(f"Duplicate campaign WOs: {sorted(duplicates)}")
            seen |= members

        expected = {str(x) for x in expected_work_orders}
        if seen != expected:
            raise RuntimeError(
                f"Campaign mismatch. Missing={sorted(expected-seen)}, Extra={sorted(seen-expected)}"
            )

    @staticmethod
    def apply_persistent_ids(campaigns, operations_by_wo):
        for campaign in campaigns:
            for wo in campaign.work_order_ids:
                for op in operations_by_wo[wo].values():
                    op.PersistentBatchID = campaign.persistent_batch_id
