import { Injectable } from '@angular/core';

export interface PushRowSnapshot {
  row: any;
  originalStart: string;
  originalEnd: string;
  originalHeatingEnd: string | null;
  originalBatchEnd: string | null;
  originalReleaseTime: string | null;
  originalMachine: string;
  originalIsManual: boolean;
  originalSource: string | null;
}

export interface BatchPushResult {
  success: boolean;
  message: string;
  pushedRows: PushRowSnapshot[];
}

export interface PushBatchRequest {
  batchDrag: any;
  targetMachine: string;
  gantt: any[];
  targetBatches: any[];
  downtimes: any[];
}

@Injectable({
  providedIn: 'root'
})
export class SchedulingEngineService {

  doesTaskOverlapDowntimeOnMachine(
    row: any,
    machine: string,
    downtimes: any[]
  ): boolean {
    const taskStart =
      new Date(row.StartTime).getTime();

    const taskEnd =
      new Date(
        row.BatchEndTime ||
        row.EndTime
      ).getTime();

    if (
      !Number.isFinite(taskStart) ||
      !Number.isFinite(taskEnd)
    ) {
      return true;
    }

    return downtimes
      .filter(
        downtime =>
          !downtime.MachineID ||
          String(downtime.MachineID) ===
            String(machine)
      )
      .some(downtime => {
        const downtimeStart =
          new Date(
            downtime.StartTime
          ).getTime();

        const downtimeEnd =
          new Date(
            downtime.EndTime
          ).getTime();

        return (
          taskStart < downtimeEnd &&
          taskEnd > downtimeStart
        );
      });
  }

  doesBatchOverlapOnMachine(
    batchDrag: any,
    targetBatches: any[]
  ): boolean {
    const draggedBatchId =
      String(
        batchDrag.batchId ||
        batchDrag.batch?.BatchID ||
        ''
      );
  
    const draggedStart =
      Math.min(
        ...batchDrag.rows.map(
          (item: any) =>
            new Date(
              item.row.StartTime
            ).getTime()
        )
      );
  
    const draggedEnd =
      Math.max(
        ...batchDrag.rows.map(
          (item: any) =>
            new Date(
              item.row.BatchEndTime ||
              item.row.EndTime
            ).getTime()
        )
      );
  
    if (
      !Number.isFinite(draggedStart) ||
      !Number.isFinite(draggedEnd)
    ) {
      return true;
    }
  
    return targetBatches.some(
      (batch: any) => {
        if (
          String(batch.BatchID) ===
          draggedBatchId
        ) {
          return false;
        }
  
        const batchStart =
          new Date(
            batch.StartTime
          ).getTime();
  
        const batchEnd =
          new Date(
            batch.BatchEndTime ||
            batch.EndTime
          ).getTime();
  
        if (
          !Number.isFinite(batchStart) ||
          !Number.isFinite(batchEnd)
        ) {
          return true;
        }
  
        return (
          draggedStart < batchEnd &&
          draggedEnd > batchStart
        );
      }
    );
  }

  createPushRowSnapshot(
    row: any
  ): PushRowSnapshot {
    return {
      row,
  
      originalStart:
        row.StartTime,
  
      originalEnd:
        row.EndTime,
  
      originalHeatingEnd:
        row.HeatingEndTime || null,
  
      originalBatchEnd:
        row.BatchEndTime || null,
  
      originalReleaseTime:
        row.ReleaseTime || null,
  
      originalMachine:
        row.AssignedMachine ||
        row.PlannedMachine,
  
      originalIsManual:
        row.IsManual === true,
  
      originalSource:
        row.Source || null
    };
  }
  
  shiftRowByMilliseconds(
    row: any,
    shiftMs: number
  ): void {
    row.StartTime =
      this.formatDateTime(
        new Date(
          row.StartTime
        ).getTime() + shiftMs
      );
  
    row.EndTime =
      this.formatDateTime(
        new Date(
          row.EndTime
        ).getTime() + shiftMs
      );
  
    if (row.HeatingEndTime) {
      row.HeatingEndTime =
        this.formatDateTime(
          new Date(
            row.HeatingEndTime
          ).getTime() + shiftMs
        );
    }
  
    if (row.BatchEndTime) {
      row.BatchEndTime =
        this.formatDateTime(
          new Date(
            row.BatchEndTime
          ).getTime() + shiftMs
        );
    }
  
    if (row.ReleaseTime) {
      row.ReleaseTime =
        this.formatDateTime(
          new Date(
            row.ReleaseTime
          ).getTime() + shiftMs
        );
    }
  }
  
  restorePushedRows(
    snapshots: PushRowSnapshot[]
  ): void {
    for (const snapshot of snapshots) {
      const row =
        snapshot.row;
  
      row.StartTime =
        snapshot.originalStart;
  
      row.EndTime =
        snapshot.originalEnd;
  
      row.HeatingEndTime =
        snapshot.originalHeatingEnd;
  
      row.BatchEndTime =
        snapshot.originalBatchEnd;
  
      row.ReleaseTime =
        snapshot.originalReleaseTime;
  
      row.AssignedMachine =
        snapshot.originalMachine;
  
      row.PlannedMachine =
        snapshot.originalMachine;
  
      row.IsManual =
        snapshot.originalIsManual;
  
      row.Source =
        snapshot.originalSource;
    }
  }

  pushBatchesForwardTransaction(
    request: PushBatchRequest
  ): BatchPushResult {
    const {
      batchDrag,
      targetMachine,
      gantt,
      targetBatches,
      downtimes
    } = request;
  
    const pushedRows: PushRowSnapshot[] = [];
  
    const visitedBatchIds =
      new Set<string>();
  
    const draggedBatchId =
      String(
        batchDrag.batchId ||
        batchDrag.batch?.BatchID ||
        ''
      );
  
    const draggedStart =
      Math.min(
        ...batchDrag.rows.map(
          (item: any) =>
            new Date(
              item.row.StartTime
            ).getTime()
        )
      );
  
    const draggedEnd =
      Math.max(
        ...batchDrag.rows.map(
          (item: any) =>
            new Date(
              item.row.BatchEndTime ||
              item.row.EndTime
            ).getTime()
        )
      );
  
    if (
      !Number.isFinite(draggedStart) ||
      !Number.isFinite(draggedEnd)
    ) {
      return {
        success: false,
        message:
          'The dragged batch has invalid dates.',
        pushedRows: []
      };
    }
  
    const otherBatches =
      targetBatches
        .filter(
          (batch: any) =>
            String(batch.BatchID) !==
            draggedBatchId
        )
        .slice()
        .sort(
          (a: any, b: any) =>
            new Date(
              a.StartTime
            ).getTime() -
            new Date(
              b.StartTime
            ).getTime()
        );
  
    const earlierBlockingBatch =
      otherBatches.find(
        (batch: any) => {
          const batchStart =
            new Date(
              batch.StartTime
            ).getTime();
  
          const batchEnd =
            new Date(
              batch.BatchEndTime ||
              batch.EndTime
            ).getTime();
  
          return (
            batchStart < draggedStart &&
            batchEnd > draggedStart
          );
        }
      );
  
    if (earlierBlockingBatch) {
      return {
        success: false,
        message:
          `Batch ${draggedBatchId} starts inside ` +
          `earlier batch ${earlierBlockingBatch.BatchID}.`,
        pushedRows: []
      };
    }
  
    const laterBatches =
      otherBatches.filter(
        (batch: any) =>
          new Date(
            batch.StartTime
          ).getTime() >= draggedStart
      );
  
    let previousEnd =
      draggedEnd;
  
    for (const batch of laterBatches) {
      const batchId =
        String(batch.BatchID);
  
      if (visitedBatchIds.has(batchId)) {
        this.restorePushedRows(
          pushedRows
        );
  
        return {
          success: false,
          message:
            `Circular push propagation detected ` +
            `for batch ${batchId}.`,
          pushedRows: []
        };
      }
  
      visitedBatchIds.add(batchId);
  
      const batchStart =
        new Date(
          batch.StartTime
        ).getTime();
  
      const batchEnd =
        new Date(
          batch.BatchEndTime ||
          batch.EndTime
        ).getTime();
  
      if (
        !Number.isFinite(batchStart) ||
        !Number.isFinite(batchEnd)
      ) {
        this.restorePushedRows(
          pushedRows
        );
  
        return {
          success: false,
          message:
            `Batch ${batchId} has invalid dates.`,
          pushedRows: []
        };
      }
  
      if (batchStart >= previousEnd) {
        break;
      }
  
      const shiftMs =
        previousEnd - batchStart;
  
      const batchRows =
        gantt.filter(
          row =>
            String(row.BatchID) ===
              batchId &&
            String(
              row.AssignedMachine ||
              row.PlannedMachine
            ) === String(targetMachine)
        );
  
      if (!batchRows.length) {
        this.restorePushedRows(
          pushedRows
        );
  
        return {
          success: false,
          message:
            `Batch ${batchId} has no operation rows.`,
          pushedRows: []
        };
      }
  
      for (const row of batchRows) {
        pushedRows.push(
          this.createPushRowSnapshot(row)
        );
  
        this.shiftRowByMilliseconds(
          row,
          shiftMs
        );
  
        row.AssignedMachine =
          targetMachine;
  
        row.PlannedMachine =
          targetMachine;
      }
  
      const downtimeConflict =
        batchRows.find(
          (row: any) =>
            this.doesTaskOverlapDowntimeOnMachine(
              row,
              targetMachine,
              downtimes
            )
        );
  
      if (downtimeConflict) {
        this.restorePushedRows(
          pushedRows
        );
  
        return {
          success: false,
          message:
            `Automatic push stopped because ` +
            `batch ${batchId} overlaps downtime ` +
            `on ${targetMachine}.`,
          pushedRows: []
        };
      }
  
      previousEnd =
        Math.max(
          ...batchRows.map(
            (row: any) =>
              new Date(
                row.BatchEndTime ||
                row.EndTime
              ).getTime()
          )
        );
    }
  
    return {
      success: true,
      message: pushedRows.length
        ? 'Later batches were pushed forward.'
        : 'No later batches required movement.',
      pushedRows
    };
  }

  private formatDateTime(
    value: number
  ): string {
    return new Date(value)
      .toISOString()
      .replace('T', ' ')
      .slice(0, 19);
  }
}