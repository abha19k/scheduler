import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class TimelineService {

  getMinTime(gantt: any[]): number {
    if (!gantt.length) {
      return Date.now();
    }

    return Math.min(
      ...gantt.map(row =>
        new Date(row.StartTime).getTime()
      )
    );
  }

  
  getMaxTime(gantt: any[]): number {
    if (!gantt.length) {
      return Date.now();
    }

    return Math.max(
      ...gantt.map(row => {
        const end = row.BatchEndTime || row.EndTime;
        return new Date(end).getTime();
      })
    );
  }

  getTimelineWidth(
    gantt: any[],
    pixelsPerHour: number
  ): number {
    if (!gantt.length) {
      return 2800;
    }

    const totalHours =
      (this.getMaxTime(gantt) - this.getMinTime(gantt)) /
      (1000 * 60 * 60);

    return Math.max(
      totalHours * pixelsPerHour + 300,
      2800
    );
  }

  generateHourTicks(
    gantt: any[],
    pixelsPerHour: number
  ): any[] {
  
    if (!gantt.length) {
      return [];
    }
  
    const min = this.getMinTime(gantt);
    const max = this.getMaxTime(gantt);
  
    const ticks = [];
  
    let current = new Date(min);
  
    current.setMinutes(0, 0, 0);
  
    while (current.getTime() <= max) {
  
      ticks.push({
        label: current.toLocaleTimeString('en-GB', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
          }),
        left:
          ((current.getTime() - min) /
            (1000 * 60 * 60)) *
          pixelsPerHour
      });
  
      current = new Date(
        current.getTime() + 60 * 60 * 1000
      );
    }
  
    return ticks;
  }

  generateDayTicks(
    gantt: any[],
    pixelsPerHour: number
  ): any[] {
  
    if (!gantt.length) {
      return [];
    }
  
    const min = this.getMinTime(gantt);
    const max = this.getMaxTime(gantt);
  
    const ticks = [];
  
    let current = new Date(min);
  
    current.setHours(0,0,0,0);
  
    while (current.getTime() <= max) {

      ticks.push({
        label: current.toLocaleDateString('en-GB', {
            day: '2-digit',
            month: 'short'
        }),
        left:
            ((current.getTime() - min) /
            (1000 * 60 * 60)) *
            pixelsPerHour,
    
        width: pixelsPerHour * 24
    });
  
  
      current.setDate(current.getDate()+1);
  
    }
  
    return ticks;
  
  }
}