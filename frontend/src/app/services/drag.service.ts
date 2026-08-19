import { Injectable } from '@angular/core';

export interface DragSnapshot {
  row: any;
  startX: number;
  startY: number;
  originalStart: number;
  originalEnd: number;
  originalHeatingEnd: number | null;
  originalBatchEnd: number | null;
  originalReleaseTime: number | null;
  originalMachine: string;
  moved: boolean;
}

export interface BatchRowSnapshot {
  row: any;
  originalStart: number;
  originalEnd: number;
  originalHeatingEnd: number | null;
  originalBatchEnd: number | null;
  originalReleaseTime: number | null;
  originalMachine: string;
}

export interface BatchDragSnapshot {
  batchId: string;
  batch: any;
  rows: BatchRowSnapshot[];
  startX: number;
  startY: number;
  moved: boolean;
}


@Injectable({
  providedIn: 'root'
})
export class DragService {
  private state: DragSnapshot | null = null;
  private readonly movementThresholdPx = 6;
  private readonly snapMinutes = 15;
  private batchState: BatchDragSnapshot | null = null;
  private snapTime(value: number): number {
    const snapMs = this.snapMinutes * 60 * 1000;

    return Math.round(value / snapMs) * snapMs;
}

  start(event: MouseEvent, row: any): DragSnapshot {
    this.state = {
      row,
      startX: event.clientX,
      startY: event.clientY,
      originalStart: this.toMillis(row.StartTime),
      originalEnd: this.toMillis(row.EndTime),
      originalHeatingEnd: this.toOptionalMillis(row.HeatingEndTime),
      originalBatchEnd: this.toOptionalMillis(row.BatchEndTime),
      originalReleaseTime: this.toOptionalMillis(row.ReleaseTime),
      originalMachine: row.AssignedMachine || row.PlannedMachine,
      moved: false
    };

    return this.state;
  }

  isDragging(): boolean {
    return this.state !== null;
  }

  getSnapshot(): DragSnapshot | null {
    return this.state;
  }

  move(clientX: number, clientY: number, pixelsPerHour: number): boolean {
    if (!this.state || pixelsPerHour <= 0) {
      return false;
    }

    const deltaX = clientX - this.state.startX;
    const deltaY = clientY - this.state.startY;

    const movedFarEnough =
        Math.abs(deltaX) >= this.movementThresholdPx ||
        Math.abs(deltaY) >= this.movementThresholdPx;

    if (!movedFarEnough) {
        return false;
    }


    const rawDeltaMs =
      (deltaX / pixelsPerHour) * 60 * 60 * 1000;
  
    const snappedStart =
        this.snapTime(this.state.originalStart + rawDeltaMs);
    
    const deltaMs =
        snappedStart - this.state.originalStart;

    this.state.moved = true;

    this.state.row.StartTime = this.formatDateTime(
      this.state.originalStart + deltaMs
    );

    this.state.row.EndTime = this.formatDateTime(
      this.state.originalEnd + deltaMs
    );

    if (this.state.originalHeatingEnd !== null) {
      this.state.row.HeatingEndTime = this.formatDateTime(
        this.state.originalHeatingEnd + deltaMs
      );
    }

    if (this.state.originalBatchEnd !== null) {
      this.state.row.BatchEndTime = this.formatDateTime(
        this.state.originalBatchEnd + deltaMs
      );
    }

    if (this.state.originalReleaseTime !== null) {
      this.state.row.ReleaseTime = this.formatDateTime(
        this.state.originalReleaseTime + deltaMs
      );
    }

    return true;
  }

  restore(): void {
    if (!this.state) {
      return;
    }

    const { row } = this.state;

    row.StartTime = this.formatDateTime(this.state.originalStart);
    row.EndTime = this.formatDateTime(this.state.originalEnd);

    if (this.state.originalHeatingEnd !== null) {
      row.HeatingEndTime = this.formatDateTime(
        this.state.originalHeatingEnd
      );
    }

    if (this.state.originalBatchEnd !== null) {
      row.BatchEndTime = this.formatDateTime(
        this.state.originalBatchEnd
      );
    }

    if (this.state.originalReleaseTime !== null) {
      row.ReleaseTime = this.formatDateTime(
        this.state.originalReleaseTime
      );
    }

    row.AssignedMachine = this.state.originalMachine;
    row.PlannedMachine = this.state.originalMachine;
  }

  finish(): DragSnapshot | null {
    const completed = this.state;
    this.state = null;
    return completed;
  }

  cancel(): void {
    this.state = null;
  }

  formatDateTime(value: number): string {
    return new Date(value)
      .toISOString()
      .replace('T', ' ')
      .slice(0, 19);
  }

  startBatch(
    event: MouseEvent,
    batch: any
  ): BatchDragSnapshot {
    const batchId = String(batch?.BatchID || '');
  
    const operations = batch?.Operations || [];
  
    this.batchState = {
      batchId,
      batch,
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
  
      rows: operations.map((row: any) => ({
        row,
        originalStart: this.toMillis(row.StartTime),
        originalEnd: this.toMillis(row.EndTime),
        originalHeatingEnd:
          this.toOptionalMillis(row.HeatingEndTime),
        originalBatchEnd:
          this.toOptionalMillis(row.BatchEndTime),
        originalReleaseTime:
          this.toOptionalMillis(row.ReleaseTime),
        originalMachine:
          row.AssignedMachine ||
          row.PlannedMachine
      }))
    };
  
    return this.batchState;
  }

  
  isBatchDragging(): boolean {
    return this.batchState !== null;
  }
  
  getBatchSnapshot(): BatchDragSnapshot | null {
    return this.batchState;
  }
  
  moveBatch(
    clientX: number,
    clientY: number,
    pixelsPerHour: number
  ): boolean {

    console.log("moveBatch()", clientX, clientY);

    if (!this.batchState || pixelsPerHour <= 0) {
      return false;
    }
  
    const deltaX =
      clientX - this.batchState.startX;
  
    const deltaY =
        clientY - this.batchState.startY;

    const movedFarEnough =
        Math.abs(deltaX) >= this.movementThresholdPx ||
        Math.abs(deltaY) >= this.movementThresholdPx;

    if (!movedFarEnough) {
        return false;
    }
  
    const rawDeltaMs =
      (deltaX / pixelsPerHour) *
      60 *
      60 *
      1000;
  
    const firstRow =
      this.batchState.rows[0];
  
    if (!firstRow) {
      return false;
    }
  
    const snappedStart =
      this.snapTime(
        firstRow.originalStart + rawDeltaMs
      );
  
    const deltaMs =
      snappedStart - firstRow.originalStart;
  
    this.batchState.moved = true;
  
    for (const item of this.batchState.rows) {
      item.row.StartTime = this.formatDateTime(
        item.originalStart + deltaMs
      );
  
      item.row.EndTime = this.formatDateTime(
        item.originalEnd + deltaMs
      );
  
      if (item.originalHeatingEnd !== null) {
        item.row.HeatingEndTime =
          this.formatDateTime(
            item.originalHeatingEnd + deltaMs
          );
      }
  
      if (item.originalBatchEnd !== null) {
        item.row.BatchEndTime =
          this.formatDateTime(
            item.originalBatchEnd + deltaMs
          );
      }
  
      if (item.originalReleaseTime !== null) {
        item.row.ReleaseTime =
          this.formatDateTime(
            item.originalReleaseTime + deltaMs
          );
      }
    }

    this.synchronizeBatchWrapper();

    console.log(
        this.batchState.rows[0].row.StartTime
      );
  
    return true;
  }
  
  restoreBatch(): void {
    if (!this.batchState) {
      return;
    }
  
    for (const item of this.batchState.rows) {
      item.row.StartTime =
        this.formatDateTime(item.originalStart);
  
      item.row.EndTime =
        this.formatDateTime(item.originalEnd);
  
      if (item.originalHeatingEnd !== null) {
        item.row.HeatingEndTime =
          this.formatDateTime(
            item.originalHeatingEnd
          );
      }
  
      if (item.originalBatchEnd !== null) {
        item.row.BatchEndTime =
          this.formatDateTime(
            item.originalBatchEnd
          );
      }
  
      if (item.originalReleaseTime !== null) {
        item.row.ReleaseTime =
          this.formatDateTime(
            item.originalReleaseTime
          );
      }
  
      item.row.AssignedMachine =
        item.originalMachine;
  
      item.row.PlannedMachine =
        item.originalMachine;
    }

    this.synchronizeBatchWrapper();
  }
  
  finishBatch(): BatchDragSnapshot | null {
    const completed = this.batchState;
    this.batchState = null;
    return completed;
  }
  
  cancelBatch(): void {
    this.batchState = null;
  }

  private synchronizeBatchWrapper(): void {
    if (!this.batchState || !this.batchState.rows.length) {
      return;
    }
  
    const rows = this.batchState.rows.map(item => item.row);
  
    const startTimes = rows
      .map(row => new Date(row.StartTime).getTime())
      .filter(value => Number.isFinite(value));
  
    const heatingEndTimes = rows
      .map(row =>
        new Date(
          row.HeatingEndTime ||
          row.EndTime
        ).getTime()
      )
      .filter(value => Number.isFinite(value));
  
    const batchEndTimes = rows
      .map(row =>
        new Date(
          row.BatchEndTime ||
          row.EndTime
        ).getTime()
      )
      .filter(value => Number.isFinite(value));
  
    if (startTimes.length) {
      this.batchState.batch.StartTime =
        this.formatDateTime(
          Math.min(...startTimes)
        );
    }
  
    if (heatingEndTimes.length) {
      this.batchState.batch.HeatingEndTime =
        this.formatDateTime(
          Math.max(...heatingEndTimes)
        );
    }
  
    if (batchEndTimes.length) {
      this.batchState.batch.BatchEndTime =
        this.formatDateTime(
          Math.max(...batchEndTimes)
        );
    }
  
    const firstRow = rows[0];
  
    this.batchState.batch.AssignedMachine =
      firstRow.AssignedMachine ||
      firstRow.PlannedMachine;
  }

  private toMillis(value: any): number {
    const result = new Date(value).getTime();

    if (!Number.isFinite(result)) {
      throw new Error(`Invalid drag date value: ${value}`);
    }

    return result;
  }

  private toOptionalMillis(value: any): number | null {
    if (!value) {
      return null;
    }

    return this.toMillis(value);
  }
}
