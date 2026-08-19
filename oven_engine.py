from __future__ import annotations

from datetime import timedelta


class OvenEngine:
    """
    PlanWise oven/heating scheduling engine.

    Core rules:
    - Campaign membership is immutable.
    - Ovens are independent and can run in parallel.
    - MaxOverSoakMinutes is a hard constraint, not an automatic reservation.
    - Oven occupation is estimated from downstream press release timing.
    - Same-oven overlap is never allowed.
    - Press prediction is read-only; actual presses are committed elsewhere.
    - All timeline writes go through TimelineManager where possible.
    """

    def __init__(
        self,
        *,
        machines,
        machine_assignment,
        params,
        planning_start,
        setup_matrix,
        calendar_details,
        operations_by_wo,
        completed,
        scheduled_rows,
        timeline,
        constraint_engine,
        calculate_setup,
        find_earliest_machine_slot,
        get_previous_operation,
        get_candidate_ovens,
        is_heating_operation,
        predict_press_start,
    ):
        self.machines = machines
        self.machine_assignment = machine_assignment
        self.params = params
        self.planning_start = planning_start
        self.setup_matrix = setup_matrix
        self.calendar_details = calendar_details
        self.operations_by_wo = operations_by_wo
        self.completed = completed
        self.scheduled_rows = scheduled_rows
        self.timeline = timeline
        self.constraints = constraint_engine

        self.calculate_setup = calculate_setup
        self.find_earliest_machine_slot = find_earliest_machine_slot
        self.get_previous_operation = get_previous_operation
        self.get_candidate_ovens = get_candidate_ovens
        self.is_heating_operation = is_heating_operation
        self.predict_press_start = predict_press_start

        # Per heating wave shadow press availability. This allows later
        # campaigns in the same heating wave to see the press queue likely
        # created by earlier campaigns, without reserving real presses yet.
        self._shadow_press_availability = {}

    # =========================================================
    # RESOURCE HELPERS
    # =========================================================

    @staticmethod
    def _machine_type(machine):
        return (getattr(machine, "MachineType", None) or "").lower()

    def _is_regular_machine(self, machine):
        return self._machine_type(machine) == "regular"

    def _candidate_presses(self, operation):
        result = []

        for machine_id, machine in self.machines.items():
            if not self._is_regular_machine(machine):
                continue

            if self.constraints.machine_can_process(operation, machine):
                result.append(machine_id)

        return sorted(result)

    def _machine_available_time(self, machine_id):
        if hasattr(self.timeline, "available_time"):
            return self.timeline.available_time(
                machine_id,
                self.planning_start,
            )

        machine = self.machines[machine_id]
        items = getattr(machine, "Timeline", []) or []
        ends = [
            item.get("EndTime")
            for item in items
            if item.get("EndTime") is not None
        ]

        if ends:
            return max(ends)

        return getattr(machine, "StartTime", None) or self.planning_start

    def _oven_idle_gap_hours(self, oven_id, oven, setup_start):
        if hasattr(self.timeline, "idle_gap_before"):
            return self.timeline.idle_gap_before(
                oven_id,
                setup_start,
                self.planning_start,
            )

        predecessor_end = max(
            [
                item["EndTime"]
                for item in (getattr(oven, "Timeline", []) or [])
                if (
                    item.get("EndTime") is not None
                    and item["EndTime"] <= setup_start
                )
            ],
            default=(
                getattr(oven, "StartTime", None)
                or self.planning_start
            ),
        )

        return max(
            0.0,
            (setup_start - predecessor_end).total_seconds() / 3600.0,
        )

    # =========================================================
    # CAMPAIGN INTEGRITY
    # =========================================================

    def _build_batch_ops(self, campaign, sequence_number):
        batch_wos = list(campaign["batch_wos"])

        if len(batch_wos) != len(set(batch_wos)):
            raise RuntimeError(
                f"Duplicate WOs inside {campaign['persistent_batch_id']}: "
                f"{batch_wos}"
            )

        batch_ops = []

        for wo in batch_wos:
            op = self.operations_by_wo[wo].get(sequence_number)
            if op is not None:
                batch_ops.append(op)

        campaign_wo_set = set(batch_wos)
        bad_wos = {
            op.WorkOrderID
            for op in batch_ops
            if op.WorkOrderID not in campaign_wo_set
        }

        if bad_wos:
            raise RuntimeError(
                f"Campaign corruption in {campaign['persistent_batch_id']}: "
                f"unexpected WOs {sorted(bad_wos)}"
            )

        return batch_ops

    # =========================================================
    # SHADOW PRESS PREDICTION
    # =========================================================

    def _shadow_state_for_wave(self, sequence_number):
        state = self._shadow_press_availability.setdefault(
            sequence_number,
            {},
        )

        result = dict(state)

        for machine_id, machine in self.machines.items():
            if not self._is_regular_machine(machine):
                continue

            result.setdefault(
                machine_id,
                self._machine_available_time(machine_id),
            )

        return result

    def _predict_batch_press_release(
        self,
        *,
        next_operations,
        heating_end,
        sequence_number,
        shadow_state=None,
    ):
        """
        Predict individual press starts and the time the last WO can leave the
        oven. Same-wave press contention is approximated with a shadow queue.
        """

        shadow = (
            dict(shadow_state)
            if shadow_state is not None
            else self._shadow_state_for_wave(sequence_number)
        )

        regular_next_ops = [
            op
            for op in next_operations
            if (
                op is not None
                and not self.is_heating_operation(op)
            )
        ]

        regular_next_ops.sort(
            key=lambda op: (
                getattr(op, "DueDate", None),
                str(op.WorkOrderID),
                str(op.OperationID),
            )
        )

        rows = []

        for next_op in regular_next_ops:
            feasible_press_ids = self._candidate_presses(next_op)

            if not feasible_press_ids:
                continue

            # Existing press decoder already knows calendars and setup. It is
            # read-only here, so use its start as a lower bound.
            independent_prediction = self.predict_press_start(
                next_op,
                heating_end,
            )

            best = None

            for press_id in feasible_press_ids:
                press_ready = max(
                    shadow.get(press_id, self.planning_start),
                    heating_end,
                )

                predicted_start = press_ready

                if independent_prediction is not None:
                    predicted_start = max(
                        predicted_start,
                        independent_prediction,
                    )

                predicted_end = (
                    predicted_start
                    + timedelta(hours=float(next_op.DurationHours))
                )

                candidate = (
                    predicted_start,
                    predicted_end,
                    press_id,
                )

                if best is None or candidate < best:
                    best = candidate

            predicted_start, predicted_end, press_id = best
            shadow[press_id] = predicted_end

            wait_minutes = max(
                0.0,
                (predicted_start - heating_end).total_seconds() / 60.0,
            )

            rows.append({
                "WorkOrderID": str(next_op.WorkOrderID),
                "OperationID": str(next_op.OperationID),
                "PredictedPress": press_id,
                "PredictedStart": predicted_start,
                "PredictedEnd": predicted_end,
                "WaitingMinutes": wait_minutes,
            })

        if not rows:
            return {
                "ReleaseTime": heating_end,
                "MaxWaitMinutes": 0.0,
                "TotalWaitMinutes": 0.0,
                "Rows": [],
                "ShadowAfter": shadow,
                "SafetyBufferMinutes": 0.0,
            }

        waits = [row["WaitingMinutes"] for row in rows]
        release_time = max(row["PredictedStart"] for row in rows)

        # Small, data-driven temporary safety margin. Never reserve the entire
        # MaxOverSoak allowance. One downstream operation duration is enough to
        # protect against small prediction differences without creating huge
        # artificial oven gaps.
        max_next_duration_minutes = max(
            float(op.DurationHours) * 60.0
            for op in regular_next_ops
        )

        remaining_oversoak_headroom = max(
            0.0,
            float(self.params.MaxOverSoakMinutes) - max(waits),
        )

        # ---------------------------------------------------------
        # SMALL PREDICTION SAFETY BUFFER
        #
        # We deliberately do NOT use MaxOverSoakMinutes as the
        # reservation duration.
        #
        # The buffer only protects against small differences between
        # predicted and actual press sequencing/setup.
        # ---------------------------------------------------------

        configured_buffer = float(
            getattr(
                self.params,
                "OvenPredictionBufferMinutes",
                30,
            )
        )

        remaining_oversoak_slack = max(
            0.0,
            float(self.params.MaxOverSoakMinutes)
            - max(waits),
        )

        safety_buffer_minutes = min(
            configured_buffer,
            remaining_oversoak_slack,
        )


        return {
            "ReleaseTime": release_time,
            "MaxWaitMinutes": max(waits),
            "TotalWaitMinutes": sum(waits),
            "Rows": rows,
            "ShadowAfter": shadow,
            "SafetyBufferMinutes": safety_buffer_minutes,
        }

    def _commit_shadow_press_plan(self, sequence_number, prediction):
        self._shadow_press_availability[sequence_number] = dict(
            prediction["ShadowAfter"]
        )

    # =========================================================
    # SAFE OVEN SLOT SEARCH
    # =========================================================

    def _find_oven_slot_for_estimated_release(
        self,
        *,
        oven,
        batch_ready_time,
        desired_setup_start,
        setup_minutes,
        heating_duration_hours,
        estimated_hold_minutes,
    ):
        """
        Search using expected physical occupation:
            setup + heating + estimated downstream hold
        rather than:
            setup + heating + MaxOverSoakMinutes
        """

        total_reserved_hours = (
            float(setup_minutes) / 60.0
            + float(heating_duration_hours)
            + max(0.0, float(estimated_hold_minutes)) / 60.0
        )

        desired_setup_start = max(
            self.planning_start,
            batch_ready_time,
            getattr(oven, "StartTime", None) or self.planning_start,
            desired_setup_start,
        )

        return self.find_earliest_machine_slot(
            oven,
            self.planning_start,
            desired_setup_start,
            total_reserved_hours,
            self.calendar_details,
        )

    # =========================================================
    # OVEN DECISION
    # =========================================================

    def choose_heating_decision(
        self,
        *,
        batch_ops,
        batch_ready_time,
        next_operations,
        preferred_oven_id,
        sequence_number,
        forced_oven_id=None,
    ):
        if not batch_ops:
            return None

        representative = batch_ops[0]
        heating_duration_hours = max(
            float(op.DurationHours)
            for op in batch_ops
        )

        candidate_ids = []

        for oven_id in self.get_candidate_ovens(representative):
            oven = self.machines[oven_id]

            if not all(
                self.constraints.machine_can_process(op, oven)
                for op in batch_ops
            ):
                continue

            if not self.constraints.batch_capacity_ok(batch_ops, oven):
                continue

            candidate_ids.append(oven_id)

        if not candidate_ids:
            return None

        # ---------------------------------------------------------
        # HARD CAMPAIGN OVEN LOCK
        # ---------------------------------------------------------
        if forced_oven_id is not None:
            if forced_oven_id not in candidate_ids:
                return None

            candidate_ids = [
                forced_oven_id
            ]

        
        # Put the CampaignBuilder / GA selected oven first only
        # when the campaign has not yet been hard-locked to an oven.
        if (
            forced_oven_id is None
            and preferred_oven_id in candidate_ids
        ):
            candidate_ids = [
                preferred_oven_id,
                *[
                    oven_id
                    for oven_id in candidate_ids
                    if oven_id != preferred_oven_id
                ],
            ]


        best_decision = None
        best_score = None
        candidate_explanations = {}
        base_shadow = self._shadow_state_for_wave(sequence_number)

        for oven_id in candidate_ids:
            oven = self.machines[oven_id]

            # 1) Rough heating-only slot, only to identify setup predecessor.
            rough_slot = self.find_earliest_machine_slot(
                oven,
                self.planning_start,
                batch_ready_time,
                heating_duration_hours,
                self.calendar_details,
            )

            previous_op = self.get_previous_operation(
                oven,
                rough_slot,
            )

            (
                total_setup,
                family_setup,
                width_setup,
                temperature_setup,
            ) = self.calculate_setup(
                previous_op,
                representative,
                self.setup_matrix,
                self.params,
            )


            heating_only_block_hours = (
                float(total_setup) / 60.0
                + heating_duration_hours
            )

            setup_start = self.find_earliest_machine_slot(
                oven,
                self.planning_start,
                batch_ready_time,
                heating_only_block_hours,
                self.calendar_details,
            )

            # Iterate because heating_end influences downstream release, and
            # downstream release influences how much oven space is required.
            for _ in range(4):
                production_start = (
                    setup_start
                    + timedelta(minutes=float(total_setup))
                )

                heating_end = (
                    production_start
                    + timedelta(hours=heating_duration_hours)
                )

                prediction = self._predict_batch_press_release(
                    next_operations=next_operations,
                    heating_end=heating_end,
                    sequence_number=sequence_number,
                    shadow_state=base_shadow,
                )

                max_wait = float(prediction["MaxWaitMinutes"])

                # If predicted wait breaches the hard limit, move heating later
                # only by the excess amount. Do not JIT-delay it unnecessarily.
                excess_wait = max(
                    0.0,
                    max_wait - float(self.params.MaxOverSoakMinutes),
                )

                desired_setup_start = (
                    setup_start
                    + timedelta(minutes=excess_wait)
                )

                estimated_hold_minutes = max(
                    0.0,
                    (
                        prediction["ReleaseTime"] - heating_end
                    ).total_seconds() / 60.0,
                )

                estimated_hold_minutes += float(
                    prediction["SafetyBufferMinutes"]
                )

                safe_setup_start = self._find_oven_slot_for_estimated_release(
                    oven=oven,
                    batch_ready_time=batch_ready_time,
                    desired_setup_start=desired_setup_start,
                    setup_minutes=total_setup,
                    heating_duration_hours=heating_duration_hours,
                    estimated_hold_minutes=estimated_hold_minutes,
                )

                if safe_setup_start == setup_start:
                    break

                setup_start = safe_setup_start

            # Final candidate timing/prediction after convergence.
            production_start = (
                setup_start
                + timedelta(minutes=float(total_setup))
            )

            heating_end = (
                production_start
                + timedelta(hours=heating_duration_hours)
            )

            prediction = self._predict_batch_press_release(
                next_operations=next_operations,
                heating_end=heating_end,
                sequence_number=sequence_number,
                shadow_state=base_shadow,
            )

            max_predicted_wait = float(prediction["MaxWaitMinutes"])
            total_predicted_wait = float(prediction["TotalWaitMinutes"])

            if (
                max_predicted_wait
                > float(self.params.MaxOverSoakMinutes) + 1e-6
            ):
                candidate_explanations[oven_id] = {
                    "Feasible": False,
                    "RejectedReason": "PredictedOverSoak",
                    "MaxPredictedWaitMinutes": round(max_predicted_wait, 2),
                    "MaxAllowedWaitMinutes": float(
                        self.params.MaxOverSoakMinutes
                    ),
                }
                continue

            predicted_release = max(
                heating_end,
                prediction["ReleaseTime"],
            )

            reservation_end = (
                predicted_release
                + timedelta(
                    minutes=float(prediction["SafetyBufferMinutes"])
                )
            )

            oven_idle_gap_hours = self._oven_idle_gap_hours(
                oven_id,
                oven,
                setup_start,
            )

            assignment_mismatches = sum(
                1
                for op in batch_ops
                if (
                    self.machine_assignment.get(op.OperationID) is not None
                    and self.machine_assignment.get(op.OperationID) != oven_id
                )
            )

            preferred_penalty = (
                0
                if (
                    preferred_oven_id is None
                    or oven_id == preferred_oven_id
                )
                else 1
            )

            # Over-soak is already a hard constraint. Among feasible options,
            # compactness comes first so ovens fill their available windows.
            score = (
                preferred_penalty,
                assignment_mismatches,
                round(max_predicted_wait, 3),
                round(total_predicted_wait, 3),
                round(oven_idle_gap_hours, 4),
                predicted_release,
                heating_end,
                round(float(total_setup), 3),
                oven_id,
            )


            explanation = {
                "Feasible": True,
                "OvenID": oven_id,
                "BatchReadyTime": batch_ready_time,
                "CurrentOvenAvailable": self._machine_available_time(oven_id),
                "SetupStart": setup_start,
                "ProductionStart": production_start,
                "HeatingEnd": heating_end,
                "PredictedRelease": predicted_release,
                "ReservationEnd": reservation_end,
                "SetupMinutes": round(float(total_setup), 2),
                "FamilySetupMinutes": round(float(family_setup), 2),
                "WidthSetupMinutes": round(float(width_setup), 2),
                "TemperatureSetupMinutes": round(
                    float(temperature_setup), 2
                ),
                "OvenIdleGapHours": round(oven_idle_gap_hours, 4),
                "MaxPredictedPressWaitMinutes": round(
                    max_predicted_wait, 2
                ),
                "TotalPredictedPressWaitMinutes": round(
                    total_predicted_wait, 2
                ),
                "SafetyBufferMinutes": round(
                    float(prediction["SafetyBufferMinutes"]), 2
                ),
                "PreferredOven": preferred_oven_id,
                "PreferredOvenPenalty": preferred_penalty,
                "AssignmentMismatches": assignment_mismatches,
                "DownstreamPredictions": prediction["Rows"],
                "Score": score,
            }

            candidate_explanations[oven_id] = explanation

            if best_score is None or score < best_score:
                best_score = score
                best_decision = {
                    "OvenID": oven_id,
                    "Oven": oven,
                    "SetupStart": setup_start,
                    "ProductionStart": production_start,
                    "HeatingEnd": heating_end,
                    "PredictedRelease": predicted_release,
                    "ReservationEnd": reservation_end,
                    "SetupMinutes": total_setup,
                    "FamilySetupMinutes": family_setup,
                    "WidthSetupMinutes": width_setup,
                    "TemperatureSetupMinutes": temperature_setup,
                    "DecoderScore": score,
                    "PressPrediction": prediction,
                    "Explanation": explanation,
                }

        if best_decision is not None:
            best_decision["CandidateExplanations"] = dict(
                candidate_explanations
            )

        return best_decision

    # =========================================================
    # COMMIT HEATING BATCH
    # =========================================================

    def commit_heating_batch(self, *, campaign, sequence_number):
        batch_ops = self._build_batch_ops(
            campaign,
            sequence_number,
        )

        if not batch_ops:
            return None

        batch_wos = list(campaign["batch_wos"])
        batch_id = campaign["batch_id"]
        persistent_batch_id = campaign["persistent_batch_id"]

        ready_times = []

        for op in batch_ops:
            if sequence_number <= 1:
                ready_time = op.EarliestStart or self.planning_start
            else:
                ready_time = self.completed.get(
                    (op.WorkOrderID, sequence_number - 1)
                )

                if ready_time is None:
                    raise ValueError(
                        f"{op.OperationID} is not ready"
                    )

            ready_times.append(ready_time)

        batch_ready_time = max(ready_times)
        next_sequence = sequence_number + 1

        next_operations = [
            self.operations_by_wo[wo].get(next_sequence)
            for wo in batch_wos
            if self.operations_by_wo[wo].get(next_sequence) is not None
        ]


        decision = self.choose_heating_decision(
            batch_ops=batch_ops,
            batch_ready_time=batch_ready_time,
            next_operations=next_operations,
            preferred_oven_id=campaign.get("preferred_oven_id"),
            sequence_number=sequence_number,
            forced_oven_id=campaign.get("locked_oven_id"),
        )


        if decision is None:
            raise RuntimeError(
                f"No feasible oven found for {batch_id} "
                f"sequence {sequence_number}"
            )

        

        representative = batch_ops[0]
        oven_id = decision["OvenID"]
        setup_start = decision["SetupStart"]
        production_start = decision["ProductionStart"]
        heating_end = decision["HeatingEnd"]
        predicted_release = max(
            heating_end,
            decision["PredictedRelease"],
        )

        batch_instance_id = f"{batch_id}_SEQ{sequence_number}"

        for op in batch_ops:
            op.BatchID = batch_instance_id
            op.PersistentBatchID = persistent_batch_id
            op.AssignedMachine = oven_id
            op.SetupStart = setup_start
            op.StartTime = production_start
            op.EndTime = heating_end
            op.HeatingEndTime = heating_end

            # Temporary predicted release. The actual press wave will overwrite
            # it in finalize_batch_release().
            op.BatchEndTime = predicted_release
            op.ReleaseTime = predicted_release

            op.SetupMinutes = (
                decision["SetupMinutes"]
                if op is representative
                else 0
            )
            op.FamilySetupMinutes = (
                decision["FamilySetupMinutes"]
                if op is representative
                else 0
            )
            op.WidthSetupMinutes = (
                decision["WidthSetupMinutes"]
                if op is representative
                else 0
            )
            op.TemperatureSetupMinutes = (
                decision["TemperatureSetupMinutes"]
                if op is representative
                else 0
            )

            op.WaitingMinutes = max(
                0.0,
                (predicted_release - heating_end).total_seconds() / 60.0,
            )
            op.OverSoakMinutes = 0
            op.OverSoakViolation = False

            due_end = op.DueDate + timedelta(days=1)
            op.Late = op.EndTime > due_end
            op.LatePenalty = (
                self.params.LateOrderPenalty if op.Late else 0
            )

            self.completed[
                (op.WorkOrderID, op.SequenceNumber)
            ] = heating_end

            self.scheduled_rows.append(op)

        timeline_item = {
            "Operation": representative,
            "SetupStart": setup_start,
            "StartTime": production_start,
            "HeatingEndTime": heating_end,
            # Predicted actual release + small safety buffer; never the full
            # MaxOverSoak allowance.
            "EndTime": decision["ReservationEnd"],
            "BatchID": batch_instance_id,
            "PersistentBatchID": persistent_batch_id,
            "BatchOperations": list(batch_ops),
            "BatchWorkOrderIDs": [
                op.WorkOrderID
                for op in batch_ops
            ],
            "IsProvisionalRelease": True,
            "DecisionExplanation": decision["Explanation"],
            "CandidateExplanations": decision["CandidateExplanations"],
        }

        self.timeline.reserve(
            oven_id,
            timeline_item,
            validate_overlap=True,
        )

        # Consume only shadow press capacity after the winning oven is committed.
        self._commit_shadow_press_plan(
            sequence_number,
            decision["PressPrediction"],
        )

        return {
            "campaign": campaign,
            "batch_ops": batch_ops,
            "oven": decision["Oven"],
            "oven_id": oven_id,
            "timeline_item": timeline_item,
            "heating_end": heating_end,
            "next_sequence": next_sequence,
            "decision": decision,
        }

    # =========================================================
    # FINAL ACTUAL RELEASE
    # =========================================================

    def _set_actual_timeline_end(
        self,
        oven_id,
        timeline_item,
        actual_release,
    ):
        """
        Finalize actual oven release.

        If the real release extends beyond the provisional
        prediction, keep the real physical release time.

        Do NOT crash the optimizer.

        Any overlap created by the prediction miss will be
        detected by machine_engine.py final validation and the
        GA will treat that chromosome as infeasible.
        """

        timeline_item["EndTime"] = (
            actual_release
        )

        timeline_item[
            "IsProvisionalRelease"
        ] = False

        timeline_item[
            "ActualReleaseTime"
        ] = actual_release


    def finalize_batch_release(
        self,
        heating_result,
        releases_by_work_order,
    ):
        batch_ops = heating_result["batch_ops"]
        heating_end = heating_result["heating_end"]

        for heating_op in batch_ops:
            release_time = releases_by_work_order.get(
                heating_op.WorkOrderID,
                heating_end,
            )

            release_time = max(
                heating_end,
                release_time,
            )

            heating_op.BatchEndTime = release_time
            heating_op.ReleaseTime = release_time
            heating_op.WaitingMinutes = max(
                0.0,
                (release_time - heating_end).total_seconds() / 60.0,
            )

        actual_oven_release = max(
            [
                getattr(op, "BatchEndTime", heating_end)
                for op in batch_ops
            ],
            default=heating_end,
        )

        timeline_item = heating_result["timeline_item"]
        oven_id = heating_result["oven_id"]

        self._set_actual_timeline_end(
            oven_id,
            timeline_item,
            actual_oven_release,
        )

        timeline_item["IsProvisionalRelease"] = False
        timeline_item["ActualReleaseTime"] = actual_oven_release

        return actual_oven_release
