import { Injectable } from '@angular/core';

export interface ScheduleSynchronizationResult {
  plannedTasks: any[];
  schedule: any[];
  workOrderSequence: any[];
}

@Injectable({
  providedIn: 'root'
})
export class ScheduleSynchronizationService {

  synchronize(
    gantt: any[]
  ): ScheduleSynchronizationResult {
    const plannedTasks =
      gantt.map(task => ({
        ...task,
        PlannedMachine:
          task.AssignedMachine ||
          task.PlannedMachine
      }));

    const schedule =
      gantt.map(task => ({
        WorkOrderID:
          task.WorkOrderID,

        OperationID:
          task.OperationID,

        BatchID:
          task.BatchID,

        AssignedMachine:
          task.AssignedMachine ||
          task.PlannedMachine,

        StartTime:
          task.StartTime,

        EndTime:
          task.EndTime,

        BatchEndTime:
          task.BatchEndTime || null,

        Late:
          task.ViolationReasons
            ?.includes('LATE') || false,

        OverSoakViolation:
          task.ViolationReasons
            ?.includes('OVER_SOAK') || false
      }));

    const workOrderSequence = [
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

    return {
      plannedTasks,
      schedule,
      workOrderSequence
    };
  }
}