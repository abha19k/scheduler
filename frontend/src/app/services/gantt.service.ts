import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class GanttService {
  private batchCache =
    new Map<string, any>();

  clearBatchCache(): void {
    this.batchCache.clear();
  }

  getMachines(
    gantt: any[]
  ): string[] {
    return [
      ...new Set(
        gantt.map(
          row => row.AssignedMachine
        )
      )
    ].sort();
  }

  getRowsForMachine(
    gantt: any[],
    machine: string
  ): any[] {
    return gantt
      .filter(
        row =>
          row.AssignedMachine === machine
      )
      .sort(
        (a, b) =>
          new Date(
            a.StartTime
          ).getTime() -
          new Date(
            b.StartTime
          ).getTime()
      );
  }

  getBatchGroupsForMachine(
    gantt: any[],
    machine: string
  ): any[] {
    const rows =
      this.getRowsForMachine(
        gantt,
        machine
      ).filter(row => row.BatchID);

    const batchIds = [
      ...new Set(
        rows.map(row =>
          String(row.BatchID)
        )
      )
    ];

    const result: any[] = [];

    for (const batchId of batchIds) {
      const batchRows = rows.filter(
        row =>
          String(row.BatchID) ===
          batchId
      );

      if (!batchRows.length) {
        continue;
      }

      const batchKey = batchId;

      let batch =
        this.batchCache.get(
          batchKey
        );

      if (!batch) {
        batch = {
          BatchID: batchId,
          AssignedMachine: machine,
          StartTime: null,
          HeatingEndTime: null,
          BatchEndTime: null,
          Operations: []
        };

        this.batchCache.set(
          batchKey,
          batch
        );
      }

      batch.BatchID = batchId;
      batch.AssignedMachine = machine;

      batch.Operations.length = 0;

      const uniqueWorkOrders =
        new Set<string>();

      for (const row of batchRows) {
        const workOrderId =
          String(row.WorkOrderID);

        if (
          uniqueWorkOrders.has(
            workOrderId
          )
        ) {
          continue;
        }

        uniqueWorkOrders.add(
          workOrderId
        );

        batch.Operations.push(row);
      }

      batch.Operations.sort(
        (a: any, b: any) =>
          String(a.WorkOrderID)
            .localeCompare(
              String(
                b.WorkOrderID
              )
            )
      );

      const startTimes =
        batchRows
          .map(row =>
            new Date(
              row.StartTime
            ).getTime()
          )
          .filter(value =>
            Number.isFinite(value)
          );

      const heatingEndTimes =
        batchRows
          .map(row =>
            new Date(
              row.HeatingEndTime ||
              row.EndTime
            ).getTime()
          )
          .filter(value =>
            Number.isFinite(value)
          );

      const batchEndTimes =
        batchRows
          .map(row =>
            new Date(
              row.BatchEndTime ||
              row.EndTime
            ).getTime()
          )
          .filter(value =>
            Number.isFinite(value)
          );

      batch.StartTime =
        startTimes.length
          ? this.formatDateTime(
              Math.min(
                ...startTimes
              )
            )
          : batchRows[0].StartTime;

      batch.HeatingEndTime =
        heatingEndTimes.length
          ? this.formatDateTime(
              Math.max(
                ...heatingEndTimes
              )
            )
          : (
              batchRows[0]
                .HeatingEndTime ||
              batchRows[0].EndTime
            );

      batch.BatchEndTime =
        batchEndTimes.length
          ? this.formatDateTime(
              Math.max(
                ...batchEndTimes
              )
            )
          : (
              batchRows[0]
                .BatchEndTime ||
              batchRows[0].EndTime
            );

      result.push(batch);
    }

    return result.sort(
      (a: any, b: any) =>
        new Date(
          a.StartTime
        ).getTime() -
        new Date(
          b.StartTime
        ).getTime()
    );
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