import { CommonModule } from '@angular/common';
import { Component, HostListener } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { RouterLink, RouterLinkActive } from '@angular/router';
import {
  Scenario,
  ScenarioDefinition,
  ScenarioService
} from '../../services/scenario.service';
import { TimelineService } from '../../services/timeline.service';
import { GanttService } from '../../services/gantt.service';

@Component({
  selector: 'app-solution',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    RouterLinkActive
  ],
  templateUrl: './solution.component.html',
  styleUrls: ['./solution.component.scss']
})
export class SolutionComponent {
  constructor(
    private http: HttpClient,
    public scenarioService: ScenarioService,
    private timelineService: TimelineService,
    private ganttService: GanttService
  ) {}

  loading = false;
  pixelsPerHour = 22;

  selectedScenarioId = 'BASE';

  activeScenario: Scenario | null = null;

  kpis: any = {
    feasible: '-',
    deliveryPerformance: '-',
    lateOrders: '-',
    overSoak: '-',
    ovenUtilization: '-',
    totalCost: '-'
  };

  schedule: any[] = [];
  workOrderSequence: any[] = [];
  plannedTasks: any[] = [];
  gantt: any[] = [];

  selectedRow: any = null;

  contextMenu = {
    visible: false,
    x: 0,
    y: 0,
    row: null as any
  };

  batchTooltip = {
    visible: false,
    x: 0,
    y: 0,
    batch: null as any
  };

  dragState: any = null;


  selectedWorkOrderId: string | null = null;
  mouseInsideTooltip = false;


  ngOnInit(): void {
    this.scenarioService.loadSavedScenarioResultsFromBackend();
  
    setTimeout(() => {
      const active =
        this.scenarioService.activeScenario();
  
      if (active) {
        this.selectedScenarioId = active.ScenarioID;
        this.loadScenarioIntoView(active);
        return;
      }
  
      const scenarios =
        this.scenarioService.scenarios();
  
      if (scenarios.length) {
        const latestScenario =
          scenarios[scenarios.length - 1];
  
        this.selectedScenarioId = latestScenario.ScenarioID;
        this.scenarioService.setActiveScenario(
          latestScenario.ScenarioID
        );
  
        this.loadScenarioIntoView(
          latestScenario
        );
      }
    }, 500);
  }

  zoomIn(): void {
    this.pixelsPerHour = Math.min(this.pixelsPerHour + 4, 60);
  }

  zoomOut(): void {
    this.pixelsPerHour = Math.max(this.pixelsPerHour - 4, 8);
  }

  getScenarioDefinitions(): ScenarioDefinition[] {
    return this.scenarioService.scenarioDefinitions();
  }

  getSelectedScenarioDefinition(): ScenarioDefinition | undefined {
    return this.scenarioService.getScenarioDefinition(
      this.selectedScenarioId
    );
  }

  getScenarios(): Scenario[] {
    return this.scenarioService.scenarios();
  }

  getParameterOverridesForRequest(): any {
    return this.getSelectedScenarioDefinition()?.ParameterOverrides || {};
  }

  getDowntimesForRequest(): any[] {
    return this.getSelectedScenarioDefinition()?.Downtimes || [];
  }

  getCalendarOverridesForRequest(): any {
    return this.getSelectedScenarioDefinition()?.CalendarOverrides || {};
  }

  getMachineOverridesForRequest(): any {
    return this.getSelectedScenarioDefinition()?.MachineOverrides || {};
  }

  getObjectiveOverridesForRequest(): any {
    return this.getSelectedScenarioDefinition()?.ObjectiveOverrides || {};
  }

  getImportedWorkOrders(): any[] {
    const importedData = this.scenarioService.importedData();
  
    if (!importedData || !importedData.sheets) {
      return [];
    }
  
    const possibleSheetNames = [
      'WorkOrders',
      'Work Orders',
      'Orders',
      'orders',
      'WorkOrder',
      'WorkOrderOperations',
      'Operations'
    ];
  
    let sheet: any = null;
  
    for (const name of possibleSheetNames) {
      if (importedData.sheets[name]) {
        sheet = importedData.sheets[name];
        break;
      }
    }
  
    if (!sheet) {
      const firstSheetName = Object.keys(importedData.sheets)[0];
      sheet = importedData.sheets[firstSheetName];
    }
  
    if (!sheet || !sheet.rows) {
      return [];
    }
  
    const grouped: any = {};
  
    for (const row of sheet.rows) {
      const workOrderId =
        row.WorkOrderID ||
        row.WorkOrderId ||
        row.WorkOrder ||
        row.OrderID ||
        row.OrderId;
  
      if (!workOrderId) {
        continue;
      }
  
      if (!grouped[workOrderId]) {
        grouped[workOrderId] = {
          WorkOrderID: workOrderId,
          DueDate: row.DueDate || row.Due || '-',
          Priority: row.Priority || '-',
          ProductFamily: row.ProductFamily || row.Family || '-',
          OperationCount: 0,
          Status: 'Imported'
        };
      }
  
      grouped[workOrderId].OperationCount += 1;
    }
  
    return Object.values(grouped);
  }

  showBatchTooltip(event: MouseEvent, batch: any): void {
    this.batchTooltip.visible = true;
    this.batchTooltip.batch = batch;
    this.batchTooltip.x = event.clientX + 14;
    this.batchTooltip.y = event.clientY + 14;
  }
  

  moveBatchTooltip(event: MouseEvent): void {

    if (!this.batchTooltip.visible) return;

    this.batchTooltip.x = event.clientX + 18;
    this.batchTooltip.y = event.clientY + 18;
  }
  
  hideBatchTooltip(): void {
    this.batchTooltip.visible = false;
    this.batchTooltip.batch = null;
  }

  scheduleHideBatchTooltip(): void {
    setTimeout(() => {
      if (!this.mouseInsideTooltip) {
        this.hideBatchTooltip();
      }
    }, 100);
  }
  
  onTooltipMouseEnter(): void {
    this.mouseInsideTooltip = true;
  }
  
  onTooltipMouseLeave(): void {
    this.mouseInsideTooltip = false;
    this.hideBatchTooltip();
  }

  onScenarioChange(event: Event): void {
    const scenarioId = (event.target as HTMLSelectElement).value;

    this.scenarioService.setActiveScenario(scenarioId);

    const selected = this.scenarioService.activeScenario();

    if (!selected) {
      return;
    }

    this.loadScenarioIntoView(selected);
  }


  cloneActiveScenario(): void {
    if (!this.activeScenario) {
      alert('Run scheduler first, then clone a scenario.');
      return;
    }

    const newScenarioId = `SCN_MANUAL_${Date.now()}`;
    const newName = `${this.activeScenario.ScenarioName} - Manual Copy`;

    this.scenarioService.cloneScenario(
      this.activeScenario.ScenarioID,
      newScenarioId,
      newName
    );

    const cloned = this.scenarioService.activeScenario();

    if (cloned) {
      this.loadScenarioIntoView(cloned);
    }
  }

  loadScenarioIntoView(scenario: Scenario): void {
    this.activeScenario = scenario;

    const k = scenario.KPIs || {};

    this.kpis = {
      feasible: k.FeasibleSchedule ?? '-',
      deliveryPerformance: k.DeliveryPerformancePercent ?? '-',
      lateOrders: k.LateOperations ?? '-',
      overSoak: k.OverSoakViolations ?? '-',
      ovenUtilization: k.OvenUtilizationPercent ?? '-',
      totalCost: k.TotalCost ?? '-'
    };

    this.plannedTasks = scenario.PlannedTasks || [];

    this.gantt = this.plannedTasks.map((row: any) => ({
      ...row,
      AssignedMachine: row.PlannedMachine || row.AssignedMachine,
      StartTime: row.StartTime,
      EndTime: row.EndTime,
      lane: row.lane || 0
    }));

    this.workOrderSequence = [
      ...new Set(
        this.gantt
          .sort(
            (a, b) =>
              new Date(a.StartTime).getTime() -
              new Date(b.StartTime).getTime()
          )
          .map(row => row.WorkOrderID)
      )
    ];

    this.schedule = this.gantt.map(row => ({
      WorkOrderID: row.WorkOrderID,
      OperationID: row.OperationID,
      BatchID: row.BatchID,
      AssignedMachine: row.AssignedMachine,
      StartTime: row.StartTime,
      EndTime: row.EndTime,
      Late: row.ViolationReasons?.includes('LATE') || false,
      OverSoakViolation: row.ViolationReasons?.includes('OVER_SOAK') || false
    }));

    this.selectedRow = null;
    this.contextMenu.visible = false;

    this.recalculateLanes();
  }

  

  runScheduler(): void {
    this.loading = true;

    this.http.post<any>(
      'http://127.0.0.1:8000/run-ga',
      {
        scenarioId: this.selectedScenarioId,
        parameterOverrides: this.getParameterOverridesForRequest(),
        downtimes: this.getDowntimesForRequest(),
        calendarOverrides: this.getCalendarOverridesForRequest(),
        machineOverrides: this.getMachineOverridesForRequest(),
        objectiveOverrides: this.getObjectiveOverridesForRequest()
      }
    ).subscribe({
      next: (response) => {
        alert('Optimizer response received');

        console.log('FULL RESPONSE:', response);

        console.table(
          this.plannedTasks.map(x => ({
            WO: x.WorkOrderID,
            Op: x.OperationID,
            Batch: x.BatchID,
            Machine: x.PlannedMachine || x.AssignedMachine,
            Start: x.StartTime,
            End: x.EndTime
          }))
        );

        this.loading = false;

        const scenario: Scenario = {
          ScenarioID: response.activeScenarioId || this.selectedScenarioId,
          ScenarioName:
            response.scenario?.ScenarioName ||
            this.getSelectedScenarioDefinition()?.ScenarioName ||
            'Scenario Result',

          CreatedBy: response.scenario?.CreatedBy,
          CreatedDate: response.scenario?.CreatedDate,
          BaseScenarioID: response.scenario?.BaseScenarioID,
          IsManualScenario: response.scenario?.IsManualScenario,
          KPIs: response.scenarioKpis || response.kpis,
          PlannedTasks: response.plannedTasks || [],
          ManualChanges: []
        };

        this.scenarioService.createScenario(scenario);
        this.activeScenario = scenario;

        this.workOrderSequence = response.workOrderSequence || [];
        this.schedule = response.schedule || [];
        this.plannedTasks = response.plannedTasks || [];

        console.table(
          this.plannedTasks
            .filter((r: any) => r.BatchID)
            .map((r: any) => ({
              WO: r.WorkOrderID,
              Op: r.OperationID,
              Batch: r.BatchID,
              Machine: r.PlannedMachine || r.AssignedMachine,
              Start: r.StartTime,
              End: r.EndTime,
              BatchEnd: r.BatchEndTime
            }))
        );
        
        const batches = new Map();
        
        this.plannedTasks
          .filter((r: any) => r.BatchID)
          .forEach((r: any) => {
            if (!batches.has(r.BatchID)) {
              batches.set(r.BatchID, new Set());
            }
        
            batches.get(r.BatchID).add(r.WorkOrderID);
          });
        
        console.log(
          [...batches.entries()].map(([batch, wos]) => ({
            Batch: batch,
            WOCount: (wos as Set<any>).size,
            WOs: [...(wos as Set<any>)].join(',')
          }))
        );

        this.gantt = this.plannedTasks.map((row: any) => ({
          ...row,
          AssignedMachine: row.PlannedMachine || row.AssignedMachine,
          StartTime: row.StartTime,
          EndTime: row.EndTime,
          lane: 0
        }));

        this.kpis = {
          feasible: response.kpis.FeasibleSchedule,
          deliveryPerformance: response.kpis.DeliveryPerformancePercent,
          lateOrders: response.kpis.LateOperations,
          overSoak: response.kpis.OverSoakViolations,
          ovenUtilization: response.kpis.OvenUtilizationPercent,
          totalCost: response.kpis.TotalCost
        };

        this.recalculateLanes();
      },

      error: (err) => {
        this.loading = false;
        console.error(err);
        alert('Scheduler failed');
      }
    });
  }

  getBatchWaitingMinutes(batch: any): number {
    if (!batch?.HeatingEndTime || !batch?.BatchEndTime) {
      return 0;
    }
  
    const heatingEnd = new Date(batch.HeatingEndTime).getTime();
    const batchEnd = new Date(batch.BatchEndTime).getTime();
  
    return Math.max(
      0,
      Math.round((batchEnd - heatingEnd) / (1000 * 60))
    );
  }
  
  formatMinutes(minutes: number): string {
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
  
    if (hours <= 0) {
      return `${remainingMinutes} min`;
    }
  
    if (remainingMinutes === 0) {
      return `${hours}h`;
    }
  
    return `${hours}h ${remainingMinutes}m`;
  }
  
  formatTooltipDate(value: any): string {
    if (!value) {
      return '-';
    }
  
    return new Date(value).toLocaleString('en-GB', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
  }
  
  getBatchTotalWeight(batch: any): number {
    return (batch?.Operations || []).reduce(
      (sum: number, op: any) =>
        sum + Number(op.Weight || 0),
      0
    );
  }
  
  getBatchTotalLength(batch: any): number {
    return (batch?.Operations || []).reduce(
      (sum: number, op: any) =>
        sum + Number(op.Length || 0),
      0
    );
  }

  getMachines(): string[] {
    return this.ganttService.getMachines(this.gantt);
  }
  
  getRowsForMachine(machine: string): any[] {
    return this.ganttService.getRowsForMachine(
      this.gantt,
      machine
    );
  }

  getBatchGroupsForMachine(machine: string): any[] {
    return this.ganttService.getBatchGroupsForMachine(
      this.gantt,
      machine
    );
  }
 
  hasBatches(machine: string): boolean {
    return this.getBatchGroupsForMachine(machine).length > 0;
  }
  
  getBatchLeft(batch: any): number {
    const start =
      new Date(batch.StartTime).getTime();
  
    const min =
      this.getMinTime();
  
    const hours =
      (start - min) / (1000 * 60 * 60);
  
    return hours * this.pixelsPerHour;
  }

  getBatchWidth(batch:any){

    const start =
        new Date(batch.StartTime).getTime();

    const end =
        new Date(batch.BatchEndTime).getTime();

    return Math.max(
        ((end-start)/(1000*60*60))
        * this.pixelsPerHour,
        60
    );
  
  }

  getHeatingWidth(batch:any){

    return (
        (
            new Date(batch.HeatingEndTime).getTime()
            -
            new Date(batch.StartTime).getTime()
        )
        /
        (1000*60*60)
    ) * this.pixelsPerHour;

  }

  getOverSoakWidth(batch:any){

    return (
        (
            new Date(batch.BatchEndTime).getTime()
            -
            new Date(batch.HeatingEndTime).getTime()
        )
        /
        (1000*60*60)
    ) * this.pixelsPerHour;

  }
  

  getOperationShortName(batch: any): string {
    const op = batch?.Operations?.[0];
  
    const operationId =
      op?.OperationID ||
      op?.Operation ||
      '';
  
    const match = String(operationId).match(/OP\d+/i);
  
    return match ? match[0].toUpperCase() : 'OP';
  }
  
  getBatchWoCount(batch: any): number {
    return batch?.Operations?.length || 0;
  }

  isRealBatch(batch: any): boolean {
    return this.getBatchWorkOrderCount(batch) > 1;
  }

  isSingleBatchRow(row: any): boolean {
    if (!row?.BatchID) {
      return false;
    }
  
    const batch = this
      .getBatchGroupsForMachine(row.AssignedMachine)
      .find((b: any) => b.BatchID === row.BatchID);
  
    if (!batch) {
      return true;
    }
  
    return this.getBatchWorkOrderCount(batch) <= 1;
  }


  isWorkOrderDimmed(workOrderId: any): boolean {
    if (!this.selectedWorkOrderId) {
      return false;
    }
  
    return (
      String(workOrderId) !==
      String(this.selectedWorkOrderId)
    );
  }

  isWorkOrderSelected(workOrderId: any): boolean {
    if (!this.selectedWorkOrderId) {
      return false;
    }
  
    return (
      String(workOrderId) ===
      String(this.selectedWorkOrderId)
    );
  }
  
  batchContainsSelectedWorkOrder(batch: any): boolean {
    if (!this.selectedWorkOrderId) {
      return false;
    }
  
    return (batch?.Operations || []).some(
      (op: any) =>
        String(op.WorkOrderID).trim() ===
        String(this.selectedWorkOrderId).trim()
    );
  }
  
  isBatchDimmedByWorkOrder(batch: any): boolean {
    if (!this.selectedWorkOrderId) {
      return false;
    }
  
    return !this.batchContainsSelectedWorkOrder(batch);
  }


  getBatchWorkOrderCount(batch: any): number {
    const unique = new Set(
      batch.Operations.map((x: any) => x.WorkOrderID)
    );
  
    return unique.size;
  }
  
  getBatchWorkOrderList(batch: any): string {
    const unique = Array.from(
      new Set(
        batch.Operations.map((x: any) => x.WorkOrderID)
      )
    );
  
    return unique.join(', ');
  }

  getUniqueBatchOperations(batch: any): any[] {
    const seen = new Set<string>();
  
    return batch.Operations.filter((op: any) => {
      const key = String(op.WorkOrderID);
  
      if (seen.has(key)) {
        return false;
      }
  
      seen.add(key);
      return true;
    });
  }

  getBatchLane(batch: any): number {
    const machine = batch.MachineID || batch.AssignedMachine || batch.Machine;
  
    const batches = this
      .getBatchGroupsForMachine(machine)
      .slice()
      .sort((a: any, b: any) =>
        new Date(a.StartTime).getTime() - new Date(b.StartTime).getTime()
      );
  
    const lanes: any[][] = [];
  
    for (const current of batches) {
      let placed = false;
  
      for (let laneIndex = 0; laneIndex < lanes.length; laneIndex++) {
        const lane = lanes[laneIndex];
  
        const overlapsLane = lane.some((existing: any) =>
          this.batchOverlaps(current, existing)
        );
  
        if (!overlapsLane) {
          lane.push(current);
  
          if (current.BatchID === batch.BatchID) {
            return laneIndex;
          }
  
          placed = true;
          break;
        }
      }
  
      if (!placed) {
        lanes.push([current]);
  
        if (current.BatchID === batch.BatchID) {
          return lanes.length - 1;
        }
      }
    }
  
    return 0;
  }
  
  getBatchTop(batch: any): number {
    return 12 + this.getBatchLane(batch) * 78;
  }
  


  getBatchHeight(batch: any): number {
    const count = this.getUniqueBatchOperations(batch).length;
    return Math.max(74, 42 + count * 26);
  }

  getVisualRowsForMachine(machine: string): any[] {
    const rows = this.getRowsForMachine(machine);
  
    return rows
      .map((row: any) => {
        const isBatchedOvenRow =
          this.isOven(row) &&
          row.BatchID;
  
        return {
          ...row,
          DisplayLabel: `WO ${row.WorkOrderID}`,
          StartTime: row.StartTime,
          EndTime: isBatchedOvenRow
            ? row.BatchEndTime || row.EndTime
            : row.EndTime,
          lane: isBatchedOvenRow
            ? this.getBatchMemberLane(row)
            : row.lane || 0
        };
      })
      .sort(
        (a: any, b: any) =>
          new Date(a.StartTime).getTime() -
          new Date(b.StartTime).getTime() ||
          (a.lane || 0) - (b.lane || 0)
      );
  }

 

  getDowntimes(): any[] {
    const scenario =
      this.getSelectedScenarioDefinition();
  
    return scenario?.Downtimes || [];
  }
  
  getDowntimesForMachine(
    machine: string
  ): any[] {
    return this.getDowntimes().filter(
      d => d.MachineID === machine
    );
  }
  
  getDowntimeLeft(downtime: any): number {
    const start = new Date(
      downtime.StartTime
    ).getTime();
  
    const min = this.getMinTime();
  
    const hours =
      (start - min) / (1000 * 60 * 60);
  
    return hours * this.pixelsPerHour;
  }
  
  getDowntimeWidth(downtime: any): number {
    const start = new Date(
      downtime.StartTime
    ).getTime();
  
    const end = new Date(
      downtime.EndTime
    ).getTime();
  
    const hours =
      (end - start) / (1000 * 60 * 60);
  
    return Math.max(
      hours * this.pixelsPerHour,
      8
    );
  }


  getMinTime(): number {
    return this.timelineService.getMinTime(this.gantt);
  }
  
  getMaxTime(): number {
    return this.timelineService.getMaxTime(this.gantt);
  }
  
  getTimelineWidth(): number {
    return this.timelineService.getTimelineWidth(
      this.gantt,
      this.pixelsPerHour
    );
  }

  getHourTicks() {
    return this.timelineService.generateHourTicks(
      this.gantt,
      this.pixelsPerHour
    );
  }
  
  getDayTicks() {
    return this.timelineService.generateDayTicks(
      this.gantt,
      this.pixelsPerHour
    );
  }


  getLeft(row: any): number {
    const start = new Date(row.StartTime).getTime();
    const min = this.getMinTime();

    const hoursFromStart = (start - min) / (1000 * 60 * 60);

    return hoursFromStart * this.pixelsPerHour;
  }

  getWidth(row: any): number {

    const start =
      new Date(
        row.StartTime
      ).getTime();
  
    const end =
      new Date(
        row.BatchEndTime ||
        row.EndTime
      ).getTime();
  
    const durationHours =
      (end - start) /
      (1000 * 60 * 60);
  
    return Math.max(
      durationHours *
        this.pixelsPerHour,
      16
    );
  }


  isOven(rowOrMachine: any): boolean {
    const value =
      typeof rowOrMachine === 'string'
        ? rowOrMachine
        : rowOrMachine?.AssignedMachine;

    return String(value || '').toLowerCase().includes('oven');
  }

  isPress(rowOrMachine: any): boolean {
    const value =
      typeof rowOrMachine === 'string'
        ? rowOrMachine
        : rowOrMachine?.AssignedMachine;

    return String(value || '').toLowerCase().includes('press');
  }


  getTop(row: any): number {
    if (this.isOven(row)) {
      return 10 + (row.lane || 0) * 34;
    }

    return 8 + (row.lane || 0) * 38;
  }

  getBatchMemberLane(row: any): number {
    if (!row?.BatchID) {
      return 0;
    }
  
    const machine =
      row.PlannedMachine ||
      row.AssignedMachine;
  
    const members = this
      .getRowsForMachine(machine)
      .filter((x: any) =>
        x.BatchID === row.BatchID
      );
  
    const uniqueWorkOrders = Array.from(
      new Set(
        members.map((x: any) =>
          String(x.WorkOrderID)
        )
      )
    ).sort();
  
    const lane = uniqueWorkOrders.indexOf(
      String(row.WorkOrderID)
    );
  
    return lane >= 0 ? lane : 0;
  }


  getBarHeight(row: any): number {
    return this.isOven(row) ? 26 : 32;
  }

  getMachineHeight(machine: string): number {
    const rows = this.getRowsForMachine(machine);
  
    if (this.isOven(machine)) {
      const batches = this.getBatchGroupsForMachine(machine);
  
      const largestBatchHeight = batches.length
        ? Math.max(
            ...batches.map((batch: any) =>
              this.getBatchHeight(batch)
            )
          )
        : 90;
  
      return Math.max(
        100,
        largestBatchHeight + 24
      );
    }
  
    const maxLane = Math.max(
      0,
      ...rows.map(row => row.lane || 0)
    );
  
    if (this.isPress(machine)) {
      return Math.max(
        80,
        52 + maxLane * 38
      );
    }
  
    return Math.max(
      80,
      52 + maxLane * 38
    );
  }


  batchOverlaps(a: any, b: any): boolean {
    const aStart = new Date(a.StartTime).getTime();
    const aEnd = new Date(a.BatchEndTime || a.EndTime).getTime();

    const bStart = new Date(b.StartTime).getTime();
    const bEnd = new Date(b.BatchEndTime || b.EndTime).getTime();

    return aStart < bEnd && aEnd > bStart;
  }

  recalculateLanes(): void {
    for (const machine of this.getMachines()) {
      const rows = this.getRowsForMachine(machine);

      if (this.isOven(machine)) {
        for (const row of rows) {
          row.lane = row.BatchID
            ? this.getBatchMemberLane(row)
            : 0;
        }

        continue;
      }

      if (this.isPress(machine)) {
        for (const row of rows) {
          row.lane = 0;
        }

        continue;
      }

      const laneEndTimes: number[] = [];

      for (const row of rows) {
        const start = new Date(row.StartTime).getTime();
        const end = new Date(row.BatchEndTime || row.EndTime).getTime();

        let assignedLane = 0;

        while (
          laneEndTimes[assignedLane] !== undefined &&
          start < laneEndTimes[assignedLane]
        ) {
          assignedLane++;
        }

        row.lane = assignedLane;
        laneEndTimes[assignedLane] = end;
      }
    }
  }


  getGanttHeight(): number {
    return this.getMachines().reduce(
      (sum, machine) => sum + this.getMachineHeight(machine),
      0
    );
  }

  getMachineTopOffset(machine: string): number {
    let top = 0;

    for (const m of this.getMachines()) {
      if (m === machine) {
        return top;
      }

      top += this.getMachineHeight(m);
    }

    return top;
  }

  getRowCenterX(row: any, side: 'start' | 'end'): number {
    const left = this.getLeft(row);
    const width = this.getWidth(row);

    return side === 'start' ? left : left + width;
  }

  getRowCenterY(row: any): number {
    const machineTop = this.getMachineTopOffset(row.AssignedMachine);
    const rowTop = this.getTop(row);
    const height = this.getBarHeight(row);

    return machineTop + rowTop + height / 2;
  }

  getPrecedenceLinks(): any[] {
    const links: any[] = [];
    const grouped: any = {};

    for (const row of this.gantt) {
      grouped[row.WorkOrderID] = grouped[row.WorkOrderID] || [];
      grouped[row.WorkOrderID].push(row);
    }

    for (const workOrderId of Object.keys(grouped)) {
      const rows = grouped[workOrderId].sort(
        (a: any, b: any) =>
          Number(a.SequenceNumber) - Number(b.SequenceNumber)
      );

      for (let i = 0; i < rows.length - 1; i++) {
        const from = rows[i];
        const to = rows[i + 1];

        links.push({
          workOrderId,
          x1: this.getRowCenterX(from, 'end'),
          y1: this.getRowCenterY(from),
          x2: this.getRowCenterX(to, 'start'),
          y2: this.getRowCenterY(to)
        });
      }
    }

    return links;
  }


  getVisiblePrecedenceLinks(): any[] {
    if (!this.selectedWorkOrderId) {
      return [];
    }
  
    return this.getPrecedenceLinks().filter(
      link =>
        String(link.workOrderId) ===
        String(this.selectedWorkOrderId)
    );
  }

  getArrowPath(link: any): string {
    const midX = link.x1 + Math.max((link.x2 - link.x1) / 2, 24);

    return `
      M ${link.x1} ${link.y1}
      C ${midX} ${link.y1},
        ${midX} ${link.y2},
        ${link.x2} ${link.y2}
    `;
  }

  selectGanttRow(event: MouseEvent, row: any): void {
    event.stopPropagation();
    this.selectedRow = row;
  }

  selectWorkOrderById(
    event: Event,
    workOrderIdValue: any
  ): void {
    event.preventDefault();
    event.stopPropagation();
  
    const workOrderId = String(workOrderIdValue ?? '').trim();
  
    if (!workOrderId) {
      return;
    }
  
    const isSameWorkOrder =
      this.selectedWorkOrderId === workOrderId;
  
    if (isSameWorkOrder) {
      this.clearSelection();
      return;
    }
  
    this.selectedWorkOrderId = workOrderId;
  
    this.selectedRow =
      this.gantt.find(
        row =>
          String(row.WorkOrderID).trim() === workOrderId
      ) || null;
  

    this.contextMenu.visible = false;
  }
  


  openContextMenu(event: MouseEvent, row: any): void {
    event.preventDefault();
    event.stopPropagation();

    this.selectedRow = row;

    this.contextMenu = {
      visible: true,
      x: event.clientX,
      y: event.clientY,
      row
    };
  }



  getAvailableMachinesForRow(row: any): string[] {
    if (!row) {
      return [];
    }
  
    return this.getMachines().filter(machine =>
      machine !== row.AssignedMachine &&
      this.canMoveRowToMachine(row, machine)
    );
  
  }
  
  changeMachine(
    row: any,
    newMachine: string
  ): void {

    if (!this.canMoveRowToMachine(row, newMachine)) {
      alert(
        'Machine change rejected. This operation type cannot run on ' +
        newMachine +
        '.'
      );
    
      return;
    }
    
    if (!row || !newMachine || !this.activeScenario) {
      return;
    }
  
    const oldMachine = row.AssignedMachine || row.PlannedMachine;
  
    if (oldMachine === newMachine) {
      return;
    }
  
    row.AssignedMachine = newMachine;
    row.PlannedMachine = newMachine;
    row.IsManual = true;
    row.Source = 'MANUAL';

    const overlappingDowntime =
      this.getOverlappingDowntime(row);

    if (overlappingDowntime) {
      row.AssignedMachine = oldMachine;
      row.PlannedMachine = oldMachine;

      alert(
        'Machine change rejected. Task overlaps downtime on ' +
        overlappingDowntime.MachineID +
        ' from ' +
        overlappingDowntime.StartTime +
        ' to ' +
        overlappingDowntime.EndTime +
        '.'
      );

      this.recalculateLanes();
      return;
    }
  
    this.plannedTasks = this.gantt.map(task => ({
      ...task,
      PlannedMachine: task.AssignedMachine || task.PlannedMachine
    }));
  
    this.schedule = this.gantt.map(task => ({
      WorkOrderID: task.WorkOrderID,
      OperationID: task.OperationID,
      BatchID: task.BatchID,
      AssignedMachine: task.AssignedMachine || task.PlannedMachine,
      StartTime: task.StartTime,
      EndTime: task.EndTime,
      Late: task.ViolationReasons?.includes('LATE') || false,
      OverSoakViolation: task.ViolationReasons?.includes('OVER_SOAK') || false
    }));
  
    this.scenarioService.updateScenarioTasks(
      this.activeScenario.ScenarioID,
      this.plannedTasks
    );
  
    this.scenarioService.addManualChange(
      this.activeScenario.ScenarioID,
      {
        ChangeType: 'MACHINE_CHANGE',
        PlannedTaskID: row.PlannedTaskID,
        WorkOrderID: row.WorkOrderID,
        OperationID: row.OperationID,
        OldValue: {
          Machine: oldMachine
        },
        NewValue: {
          Machine: newMachine
        },
        Note: `Planner changed machine from ${oldMachine} to ${newMachine}.`
      }
    );
  
    this.contextMenu.visible = false;
    this.selectedRow = row;
  
    this.recalculateLanes();
  
    this.scenarioService.saveScenarioToBackend(
      this.activeScenario.ScenarioID
    );
  }

  unplanWorkOrder(): void {
    const row = this.contextMenu.row;

    if (!row || !this.activeScenario) {
      return;
    }

    const workOrderId = row.WorkOrderID;

    const removedRows = this.gantt.filter(
      item => item.WorkOrderID === workOrderId
    );

    this.gantt = this.gantt.filter(
      item => item.WorkOrderID !== workOrderId
    );

    this.schedule = this.schedule.filter(
      item => item.WorkOrderID !== workOrderId
    );

    this.workOrderSequence = this.workOrderSequence.filter(
      item => item !== workOrderId
    );

    this.scenarioService.updateScenarioTasks(
      this.activeScenario.ScenarioID,
      this.gantt
    );

    for (const removed of removedRows) {
      this.scenarioService.addManualChange(
        this.activeScenario.ScenarioID,
        {
          ChangeType: 'UNPLAN',
          PlannedTaskID: removed.PlannedTaskID,
          WorkOrderID: removed.WorkOrderID,
          OperationID: removed.OperationID,
          OldValue: removed,
          NewValue: null,
          Note: 'Planner manually unplanned task.'
        }
      );
    }

    this.contextMenu.visible = false;
    this.selectedRow = null;

    this.recalculateLanes();

    this.scenarioService.saveScenarioToBackend(
      this.activeScenario.ScenarioID
    );
  }

  startDrag(event: MouseEvent, row: any): void {
    event.preventDefault();
    event.stopPropagation();

    this.selectedRow = row;

    this.dragState = {
      row,
      startX: event.clientX,
      originalStart: new Date(row.StartTime).getTime(),
      originalEnd: new Date(row.EndTime).getTime(),
      originalBatchEnd: row.BatchEndTime
        ? new Date(row.BatchEndTime).getTime()
        : null,
      originalMachine: row.AssignedMachine
    };
  }

  doesTaskOverlapDowntime(
    row: any
  ): boolean {
    const machine =
      row.AssignedMachine || row.PlannedMachine;
  
    const taskStart =
      new Date(row.StartTime).getTime();
  
    const taskEndValue =
      row.BatchEndTime || row.EndTime;

    const taskEnd =
      new Date(taskEndValue).getTime();
  
    const downtimes =
      this.getDowntimesForMachine(machine);
  
    return downtimes.some(downtime => {
      const downtimeStart =
        new Date(downtime.StartTime).getTime();
  
      const downtimeEnd =
        new Date(downtime.EndTime).getTime();
  
      return (
        taskStart < downtimeEnd &&
        taskEnd > downtimeStart
      );
    });
  }
  
  getOverlappingDowntime(
    row: any
  ): any | null {
    const machine =
      row.AssignedMachine || row.PlannedMachine;
  
    const taskStart =
      new Date(row.StartTime).getTime();
  
    const taskEndValue =
      row.BatchEndTime || row.EndTime;

    const taskEnd =
      new Date(taskEndValue).getTime();
  
    const downtimes =
      this.getDowntimesForMachine(machine);
  
    return downtimes.find(downtime => {
      const downtimeStart =
        new Date(downtime.StartTime).getTime();
  
      const downtimeEnd =
        new Date(downtime.EndTime).getTime();
  
      return (
        taskStart < downtimeEnd &&
        taskEnd > downtimeStart
      );
    }) || null;
  }
  
  restoreDraggedRow(): void {
    if (!this.dragState) {
      return;
    }
  
    this.dragState.row.StartTime =
      new Date(this.dragState.originalStart)
        .toISOString()
        .replace('T', ' ')
        .slice(0, 19);
  
    this.dragState.row.EndTime =
      new Date(this.dragState.originalEnd)
        .toISOString()
        .replace('T', ' ')
        .slice(0, 19);

    if (this.dragState.originalBatchEnd) {
      this.dragState.row.BatchEndTime =
        new Date(this.dragState.originalBatchEnd)
          .toISOString()
          .replace('T', ' ')
          .slice(0, 19);
    }
  
    this.dragState.row.AssignedMachine =
      this.dragState.originalMachine;
  
    this.dragState.row.PlannedMachine =
      this.dragState.originalMachine;
  
    this.recalculateLanes();
  }

  undoLastChange(): void {
    if (!this.activeScenario) {
      return;
    }
  
    const manualChanges =
      this.activeScenario.ManualChanges || [];
  
    if (!manualChanges.length) {
      alert('No manual changes to undo.');
      return;
    }
  
    const lastChange =
      manualChanges[manualChanges.length - 1];
  
    if (lastChange.ChangeType === 'MOVE') {
      const task = this.gantt.find(
        row => row.PlannedTaskID === lastChange.PlannedTaskID
      );
  
      if (!task) {
        alert('Could not find the task to undo.');
        return;
      }
  
      task.StartTime = lastChange.OldValue.StartTime;
      task.EndTime = lastChange.OldValue.EndTime;
      task.BatchEndTime = lastChange.OldValue.BatchEndTime || task.BatchEndTime;
      task.AssignedMachine = lastChange.OldValue.Machine;
      task.PlannedMachine = lastChange.OldValue.Machine;
    }
  
    if (lastChange.ChangeType === 'MACHINE_CHANGE') {
      const task = this.gantt.find(
        row => row.PlannedTaskID === lastChange.PlannedTaskID
      );
  
      if (!task) {
        alert('Could not find the task to undo.');
        return;
      }
  
      task.AssignedMachine = lastChange.OldValue.Machine;
      task.PlannedMachine = lastChange.OldValue.Machine;
    }

    if (lastChange.ChangeType === 'UNPLAN') {
      if (lastChange.OldValue) {
    
        this.gantt.push(
          structuredClone(lastChange.OldValue)
        );
    
        this.plannedTasks = [...this.gantt];
      }
    }
  
    this.activeScenario.ManualChanges =
      manualChanges.slice(0, -1);
  
    this.plannedTasks = [...this.gantt];
  
    this.schedule = this.gantt.map(row => ({
      WorkOrderID: row.WorkOrderID,
      OperationID: row.OperationID,
      AssignedMachine: row.AssignedMachine,
      StartTime: row.StartTime,
      EndTime: row.EndTime,
      Late: row.ViolationReasons?.includes('LATE') || false,
      OverSoakViolation: row.ViolationReasons?.includes('OVER_SOAK') || false
    }));
  
    this.workOrderSequence = [
      ...new Set(
        this.gantt
          .sort(
            (a, b) =>
              new Date(a.StartTime).getTime() -
              new Date(b.StartTime).getTime()
          )
          .map(row => row.WorkOrderID)
      )
    ];
  
    this.scenarioService.updateScenarioTasks(
      this.activeScenario.ScenarioID,
      this.gantt
    );
  
    this.scenarioService.saveScenarioToBackend(
      this.activeScenario.ScenarioID
    );
  
    this.recalculateLanes();
  
    alert('Last manual change undone.');
  }

  canMoveRowToMachine(
    row: any,
    machine: string
  ): boolean {
    const operationType =
      String(row.OperationType || row.OperationTypeCode || '')
        .toLowerCase();
  
    const targetMachine =
      String(machine || '').toLowerCase();
  
    const isHeatOperation =
      operationType.includes('heat') ||
      operationType.includes('oven') ||
      operationType.includes('batch');
  
    const isPressOperation =
      operationType.includes('press');
  
    const isOvenMachine =
      targetMachine.includes('oven');
  
    const isPressMachine =
      targetMachine.includes('press');
  
    if (isHeatOperation) {
      return isOvenMachine;
    }
  
    if (isPressOperation) {
      return isPressMachine;
    }
  
    return true;
  }

  @HostListener('document:mousemove', ['$event'])
  onMouseMove(event: MouseEvent): void {
    if (!this.dragState) return;

    const deltaX = event.clientX - this.dragState.startX;
    const deltaHours = deltaX / this.pixelsPerHour;
    const deltaMs = deltaHours * 60 * 60 * 1000;

    const newStart = new Date(this.dragState.originalStart + deltaMs);
    const newEnd = new Date(this.dragState.originalEnd + deltaMs);

    this.dragState.row.StartTime = newStart.toISOString().replace('T', ' ').slice(0, 19);
    this.dragState.row.EndTime = newEnd.toISOString().replace('T', ' ').slice(0, 19);

    if (this.dragState.originalBatchEnd) {
      const newBatchEnd = new Date(this.dragState.originalBatchEnd + deltaMs);
      this.dragState.row.BatchEndTime = newBatchEnd.toISOString().replace('T', ' ').slice(0, 19);
    }

    this.recalculateLanes();
  }

  @HostListener('document:mouseup')
    onMouseUp(): void {

      if (!this.dragState) {
        return;
      }

      if (!this.activeScenario) {
        this.dragState = null;
        return;
      }

      const row = this.dragState.row;

      const overlappingDowntime =
        this.getOverlappingDowntime(row);

      if (overlappingDowntime) {
        alert(
          'Move rejected. Task overlaps downtime on ' +
          overlappingDowntime.MachineID +
          ' from ' +
          overlappingDowntime.StartTime +
          ' to ' +
          overlappingDowntime.EndTime +
          '.'
        );

        this.restoreDraggedRow();
        this.dragState = null;
        return;
      }

      this.scenarioService.updateScenarioTasks(
        this.activeScenario.ScenarioID,
        this.gantt
      );

      this.scenarioService.addManualChange(
        this.activeScenario.ScenarioID,
        {
          ChangeType: 'MOVE',
          PlannedTaskID: row.PlannedTaskID,
          WorkOrderID: row.WorkOrderID,
          OperationID: row.OperationID,

          OldValue: {
            StartTime: new Date(this.dragState.originalStart)
              .toISOString()
              .replace('T', ' ')
              .slice(0, 19),

            EndTime: new Date(this.dragState.originalEnd)
              .toISOString()
              .replace('T', ' ')
              .slice(0, 19),

            BatchEndTime: this.dragState.originalBatchEnd
              ? new Date(this.dragState.originalBatchEnd)
                .toISOString()
                .replace('T', ' ')
                .slice(0, 19)
              : null,

            Machine: this.dragState.originalMachine,
          },

          NewValue: {
            StartTime: row.StartTime,
            EndTime: row.EndTime,
            BatchEndTime: row.BatchEndTime || null,
            Machine: row.AssignedMachine,
          },

          Note: 'Planner manually moved task.'
        }
      );

      this.scenarioService.saveScenarioToBackend(
        this.activeScenario.ScenarioID
      );

      this.dragState = null;
    }

    clearSelection(): void {
      this.selectedRow = null;
      this.selectedWorkOrderId = null;
      this.contextMenu.visible = false;
    }

  @HostListener('document:click', ['$event'])
    closeContextMenu(event: MouseEvent): void {
    
        const target = event.target as HTMLElement;
    
        if (target.closest('.batch-tooltip')) {
            return;
        }
    
        this.contextMenu.visible = false;
        this.hideBatchTooltip();
    }

  @HostListener('document:scroll')
    onDocumentScroll(): void {
      this.hideBatchTooltip();
    }

}