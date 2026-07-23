import { Injectable } from '@angular/core';
import { TimelineService } from '../services/timeline.service';

@Injectable({
  providedIn: 'root'
})
export class GanttService {

  getMachines(gantt: any[]): string[] {
    return [...new Set(gantt.map(row => row.AssignedMachine))].sort();
  }

  getRowsForMachine(gantt: any[], machine: string): any[] {
    return gantt
      .filter(row => row.AssignedMachine === machine)
      .sort(
        (a, b) =>
          new Date(a.StartTime).getTime() -
          new Date(b.StartTime).getTime()
      );
  }

  getBatchGroupsForMachine(gantt: any[], machine: string): any[] {
    const rows = this.getRowsForMachine(gantt, machine);
  
    const batchMap = new Map<string, any>();
  
    rows.forEach((row: any) => {
      if (!row.BatchID) {
        return;
      }
  
      const batchKey = `${machine}_${row.BatchID}`;
  
      if (!batchMap.has(batchKey)) {
        batchMap.set(batchKey,{
          BatchID: row.BatchID,
          AssignedMachine: machine,
          StartTime: row.StartTime,
          HeatingEndTime: row.HeatingEndTime || row.EndTime,      
          BatchEndTime: row.BatchEndTime || row.EndTime,
          Operations:[]
        });
      }
  
      const batch = batchMap.get(batchKey);
  
      const alreadyExists = batch.Operations.some(
        (op: any) =>
          String(op.WorkOrderID) === String(row.WorkOrderID)
      );
  
      if (!alreadyExists) {
        batch.Operations.push(row);
      }
  
      if (
        new Date(row.StartTime).getTime() <
        new Date(batch.StartTime).getTime()
      ) {
        batch.StartTime = row.StartTime;
      }

      const heatingEnd =
          row.HeatingEndTime || row.EndTime;

      if (
          new Date(heatingEnd).getTime() >
          new Date(batch.HeatingEndTime).getTime()
      ) {
          batch.HeatingEndTime = heatingEnd;
      }
        

    
      const visualEnd =
        row.BatchEndTime || row.EndTime;
    
      if(
          new Date(visualEnd) >
          new Date(batch.BatchEndTime)
      ){
          batch.BatchEndTime = visualEnd;
      }
    });

    const result = Array.from(batchMap.values())
      .map((batch: any) => ({
        ...batch,
        Operations: batch.Operations.sort(
          (a: any, b: any) =>
            String(a.WorkOrderID).localeCompare(String(b.WorkOrderID))
        )
      }))
      .sort(
        (a: any, b: any) =>
          new Date(a.StartTime).getTime() -
          new Date(b.StartTime).getTime()
      );


    return result;
  
  }


}