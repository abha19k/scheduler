import { Injectable } from '@angular/core';
import {
  ManualChange,
  Scenario,
  ScenarioService
} from './scenario.service';

import {
    BatchPushResult
  } from './scheduling-engine.service';

export interface UndoRequest {
  scenario: Scenario;
  gantt: any[];
}

export interface UndoResult {
  success: boolean;
  message: string;

  /*
   * The restored Gantt rows.
   *
   * A new array reference is returned so Angular
   * can refresh the view reliably.
   */
  gantt: any[];

  /*
   * The change that was restored.
   */
  restoredChange: ManualChange | null;
}

export interface RecordBatchMoveRequest {
    scenarioId: string;
    batchDrag: any;
    pushResult: BatchPushResult;
    formatDateTime:
      (value: number) => string;
  }

@Injectable({
  providedIn: 'root'
})
export class ManualChangeService {
    
    constructor(
        private scenarioService:
        ScenarioService
    ) {}  


    recordBatchMove(
        request: RecordBatchMoveRequest
      ): void {
        const {
          scenarioId,
          batchDrag,
          pushResult,
          formatDateTime
        } = request;
      
        this.scenarioService.addManualChange(
          scenarioId,
          {
            ChangeType: 'BATCH_MOVE',
            BatchID:
              batchDrag.batch.BatchID,
      
            OldValue: [
              ...batchDrag.rows.map(
                (item: any) => ({
                  PlannedTaskID:
                    item.row.PlannedTaskID,
      
                  BatchID:
                    item.row.BatchID,
      
                  StartTime:
                    formatDateTime(
                      item.originalStart
                    ),
      
                  EndTime:
                    formatDateTime(
                      item.originalEnd
                    ),
      
                  HeatingEndTime:
                    item.originalHeatingEnd !== null
                      ? formatDateTime(
                          item.originalHeatingEnd
                        )
                      : null,
      
                  BatchEndTime:
                    item.originalBatchEnd !== null
                      ? formatDateTime(
                          item.originalBatchEnd
                        )
                      : null,
      
                  ReleaseTime:
                    item.originalReleaseTime !== null
                      ? formatDateTime(
                          item.originalReleaseTime
                        )
                      : null,
      
                  Machine:
                    item.originalMachine,
      
                  ChangeRole:
                    'DRAGGED'
                })
              ),
      
              ...pushResult.pushedRows.map(
                snapshot => ({
                  PlannedTaskID:
                    snapshot.row.PlannedTaskID,
      
                  BatchID:
                    snapshot.row.BatchID,
      
                  StartTime:
                    snapshot.originalStart,
      
                  EndTime:
                    snapshot.originalEnd,
      
                  HeatingEndTime:
                    snapshot.originalHeatingEnd,
      
                  BatchEndTime:
                    snapshot.originalBatchEnd,
      
                  ReleaseTime:
                    snapshot.originalReleaseTime,
      
                  Machine:
                    snapshot.originalMachine,
      
                  ChangeRole:
                    'AUTO_PUSHED',
      
                  IsManual:
                    snapshot.originalIsManual,
      
                  Source:
                    snapshot.originalSource
                })
              )
            ],
      
            NewValue: [
              ...batchDrag.rows.map(
                (item: any) => ({
                  PlannedTaskID:
                    item.row.PlannedTaskID,
      
                  BatchID:
                    item.row.BatchID,
      
                  StartTime:
                    item.row.StartTime,
      
                  EndTime:
                    item.row.EndTime,
      
                  HeatingEndTime:
                    item.row.HeatingEndTime ||
                    null,
      
                  BatchEndTime:
                    item.row.BatchEndTime ||
                    null,
      
                  ReleaseTime:
                    item.row.ReleaseTime ||
                    null,
      
                  Machine:
                    item.row.AssignedMachine,
      
                  ChangeRole:
                    'DRAGGED'
                })
              ),
      
              ...pushResult.pushedRows.map(
                snapshot => ({
                  PlannedTaskID:
                    snapshot.row.PlannedTaskID,
      
                  BatchID:
                    snapshot.row.BatchID,
      
                  StartTime:
                    snapshot.row.StartTime,
      
                  EndTime:
                    snapshot.row.EndTime,
      
                  HeatingEndTime:
                    snapshot.row.HeatingEndTime ||
                    null,
      
                  BatchEndTime:
                    snapshot.row.BatchEndTime ||
                    null,
      
                  ReleaseTime:
                    snapshot.row.ReleaseTime ||
                    null,
      
                  Machine:
                    snapshot.row.AssignedMachine,
      
                  ChangeRole:
                    'AUTO_PUSHED',
      
                  IsManual:
                    snapshot.row.IsManual === true,
      
                  Source:
                    snapshot.row.Source || null
                })
              )
            ],
      
            Note:
              pushResult.pushedRows.length
                ? (
                    `Planner moved batch ` +
                    `${batchDrag.batch.BatchID}; ` +
                    `${pushResult.pushedRows.length} ` +
                    `downstream operation rows were ` +
                    `automatically pushed.`
                  )
                : (
                    `Planner manually moved batch ` +
                    `${batchDrag.batch.BatchID}.`
                  )
          }
        );
      }
      
      
    getLastManualChange(
        scenario: Scenario | null
    ): ManualChange | null {
        if (!scenario) {
        return null;
        }

        const manualChanges =
        scenario.ManualChanges || [];

        if (!manualChanges.length) {
        return null;
        }

        return manualChanges[
        manualChanges.length - 1
        ];
    }

    undoLastChange(
        scenario: Scenario,
        gantt: any[]
    ): UndoResult {
        const lastChange =
        this.getLastManualChange(
            scenario
        );
    
        if (!lastChange) {
        return {
            success: false,
            message:
            'No manual changes to undo.',
            gantt,
            restoredChange: null
        };
        }
    
        switch (lastChange.ChangeType) {
        case 'MOVE':
            return this.undoMove(
            lastChange,
            gantt
            );
    
        case 'MACHINE_CHANGE':
            return this.undoMachineChange(
            lastChange,
            gantt
            );
    
        case 'UNPLAN':
            return this.undoUnplan(
            lastChange,
            gantt
            );
    
        case 'BATCH_MOVE':
            return this.undoBatchMove(
            lastChange,
            gantt
            );
    
        case 'BATCH_MACHINE_CHANGE':
            return this.undoBatchMachineChange(
            lastChange,
            gantt
            );
    
        case 'BATCH_UNPLAN':
            return this.undoBatchUnplan(
            lastChange,
            gantt
            );
    
        default:
            return {
            success: false,
            message:
                `Undo is not implemented for change type: ` +
                `${lastChange.ChangeType}`,
            gantt,
            restoredChange: null
            };
        }
    }

    undoMove(
        change: ManualChange,
        gantt: any[]
    ): UndoResult {
        const task =
        gantt.find(
            row =>
            String(row.PlannedTaskID) ===
            String(change.PlannedTaskID)
        );
    
        if (!task) {
        return {
            success: false,
            message:
            'Could not find the moved task to undo.',
            gantt,
            restoredChange: null
        };
        }
    
        const oldValue =
        change.OldValue;
    
        if (!oldValue) {
        return {
            success: false,
            message:
            'The previous task position is missing.',
            gantt,
            restoredChange: null
        };
        }
    
        task.StartTime =
        oldValue.StartTime;
    
        task.EndTime =
        oldValue.EndTime;
    
        if (
        oldValue.HeatingEndTime !==
        undefined
        ) {
        task.HeatingEndTime =
            oldValue.HeatingEndTime;
        }
    
        if (
        oldValue.BatchEndTime !==
        undefined
        ) {
        task.BatchEndTime =
            oldValue.BatchEndTime;
        }
    
        if (
        oldValue.ReleaseTime !==
        undefined
        ) {
        task.ReleaseTime =
            oldValue.ReleaseTime;
        }
    
        if (oldValue.Machine) {
        task.AssignedMachine =
            oldValue.Machine;
    
        task.PlannedMachine =
            oldValue.Machine;
        }
    
        if (
        oldValue.IsManual !== undefined
        ) {
        task.IsManual =
            oldValue.IsManual;
        }
    
        if (
        oldValue.Source !== undefined
        ) {
        task.Source =
            oldValue.Source;
        }
    
        return {
        success: true,
        message:
            'Task move restored.',
        gantt: [...gantt],
        restoredChange: change
        };
    }

    undoMachineChange(
        change: ManualChange,
        gantt: any[]
    ): UndoResult {
        const task =
        gantt.find(
            row =>
            String(row.PlannedTaskID) ===
            String(change.PlannedTaskID)
        );
    
        if (!task) {
        return {
            success: false,
            message:
            'Could not find the task whose machine was changed.',
            gantt,
            restoredChange: null
        };
        }
    
        const oldMachine =
        change.OldValue?.Machine;
    
        if (!oldMachine) {
        return {
            success: false,
            message:
            'The previous machine is missing.',
            gantt,
            restoredChange: null
        };
        }
    
        task.AssignedMachine =
        oldMachine;
    
        task.PlannedMachine =
        oldMachine;
    
        if (
        change.OldValue?.IsManual !==
        undefined
        ) {
        task.IsManual =
            change.OldValue.IsManual;
        }
    
        if (
        change.OldValue?.Source !==
        undefined
        ) {
        task.Source =
            change.OldValue.Source;
        }
    
        return {
        success: true,
        message:
            'Machine change restored.',
        gantt: [...gantt],
        restoredChange: change
        };
    }

    undoUnplan(
        change: ManualChange,
        gantt: any[]
    ): UndoResult {
        if (!change.OldValue) {
        return {
            success: false,
            message:
            'The removed task data is missing.',
            gantt,
            restoredChange: null
        };
        }
    
        const restoredTask =
        structuredClone(
            change.OldValue
        );
    
        const alreadyExists =
        gantt.some(
            row =>
            String(row.PlannedTaskID) ===
            String(
                restoredTask.PlannedTaskID
            )
        );
    
        if (!alreadyExists) {
        gantt.push(
            restoredTask
        );
        }
    
        return {
        success: true,
        message:
            'Unplanned task restored.',
        gantt: [...gantt],
        restoredChange: change
        };
    }

    undoBatchMove(
        change: ManualChange,
        gantt: any[]
    ): UndoResult {
        const oldRows =
        Array.isArray(
            change.OldValue
        )
            ? change.OldValue
            : [];
    
        if (!oldRows.length) {
        return {
            success: false,
            message:
            'The previous batch positions are missing.',
            gantt,
            restoredChange: null
        };
        }
    
        let restoredRows = 0;
    
        for (const oldValue of oldRows) {
        const task =
            gantt.find(
            row =>
                String(row.PlannedTaskID) ===
                String(
                oldValue.PlannedTaskID
                )
            );
    
        if (!task) {
            console.warn(
            'Could not find task during batch undo:',
            oldValue.PlannedTaskID
            );
    
            continue;
        }
    
        task.StartTime =
            oldValue.StartTime;
    
        task.EndTime =
            oldValue.EndTime;
    
        task.HeatingEndTime =
            oldValue.HeatingEndTime;
    
        task.BatchEndTime =
            oldValue.BatchEndTime;
    
        task.ReleaseTime =
            oldValue.ReleaseTime;
    
        if (oldValue.Machine) {
            task.AssignedMachine =
            oldValue.Machine;
    
            task.PlannedMachine =
            oldValue.Machine;
        }
    
        if (
            oldValue.IsManual !==
            undefined
        ) {
            task.IsManual =
            oldValue.IsManual;
        }
    
        if (
            oldValue.Source !==
            undefined
        ) {
            task.Source =
            oldValue.Source;
        }
    
        restoredRows++;
        }
    
        if (!restoredRows) {
        return {
            success: false,
            message:
            'None of the batch rows could be restored.',
            gantt,
            restoredChange: null
        };
        }
    
        return {
        success: true,
        message:
            'Batch move restored.',
        gantt: [...gantt],
        restoredChange: change
        };
    }

    undoBatchMachineChange(
        change: ManualChange,
        gantt: any[]
    ): UndoResult {
        const batchId =
        String(
            change.BatchID || ''
        );
    
        const oldMachine =
        change.OldValue?.Machine;
    
        if (
        !batchId ||
        !oldMachine
        ) {
        return {
            success: false,
            message:
            'The previous batch machine information is missing.',
            gantt,
            restoredChange: null
        };
        }
    
        const batchRows =
        gantt.filter(
            row =>
            String(row.BatchID) ===
            batchId
        );
    
        if (!batchRows.length) {
        return {
            success: false,
            message:
            `Could not find batch ${batchId}.`,
            gantt,
            restoredChange: null
        };
        }
    
        for (const row of batchRows) {
        row.AssignedMachine =
            oldMachine;
    
        row.PlannedMachine =
            oldMachine;
    
        if (
            change.OldValue?.IsManual !==
            undefined
        ) {
            row.IsManual =
            change.OldValue.IsManual;
        }
    
        if (
            change.OldValue?.Source !==
            undefined
        ) {
            row.Source =
            change.OldValue.Source;
        }
        }
    
        return {
        success: true,
        message:
            'Batch machine change restored.',
        gantt: [...gantt],
        restoredChange: change
        };
    }

    undoBatchUnplan(
        change: ManualChange,
        gantt: any[]
    ): UndoResult {
        const removedRows =
        Array.isArray(
            change.OldValue
        )
            ? change.OldValue
            : [];
    
        if (!removedRows.length) {
        return {
            success: false,
            message:
            'The removed batch data is missing.',
            gantt,
            restoredChange: null
        };
        }
    
        for (const removedRow of removedRows) {
        const alreadyExists =
            gantt.some(
            row =>
                String(row.PlannedTaskID) ===
                String(
                removedRow.PlannedTaskID
                )
            );
    
        if (!alreadyExists) {
            gantt.push(
            structuredClone(
                removedRow
            )
            );
        }
        }
    
        return {
        success: true,
        message:
            'Unplanned batch restored.',
        gantt: [...gantt],
        restoredChange: change
        };
    }

    buildWorkOrderSequence(
        gantt: any[]
    ): any[] {
        return [
        ...new Set(
            [...gantt]
            .sort(
                (a, b) =>
                new Date(
                    a.StartTime
                ).getTime() -
                new Date(
                    b.StartTime
                ).getTime()
            )
            .map(
                row =>
                row.WorkOrderID
            )
        )
        ];
    }
}