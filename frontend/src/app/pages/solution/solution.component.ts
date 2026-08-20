import { CommonModule } from '@angular/common';
import { Component, HostListener, ElementRef, ViewChild } from '@angular/core';
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
import { DragService } from '../../services/drag.service';

import {
  SchedulingEngineService,
  PushRowSnapshot,
  BatchPushResult
} from '../../services/scheduling-engine.service';

import {
  ManualChangeService
} from '../../services/manual-change.service';

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

  @ViewChild('ganttBoard')
  ganttBoard!: ElementRef<HTMLDivElement>;

  constructor(
    private http: HttpClient,
    public scenarioService: ScenarioService,
    private timelineService: TimelineService,
    private ganttService: GanttService,
    public dragService: DragService,
    private schedulingEngine:
      SchedulingEngineService,
    private manualChangeService:
      ManualChangeService
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
  selectedBatch: any = null;

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

  dragValidation = {
    valid: true,
    message: ''
  };

  dragTarget = {
    machine: null as string | null,
    valid: true,
    message: ''
  };

  batchContextMenu = {
    visible: false,
    x: 0,
    y: 0,
    batch: null as any
  };

  selectedWorkOrderId: string | null = null;
  mouseInsideTooltip = false;

  timelineMinTime = 0;
  timelineMaxTime = 0;


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


  showBatchTooltip(
    event: MouseEvent,
    batch: any
  ): void {
    if (
      this.dragService.isBatchDragging() ||
      this.batchContextMenu.visible ||
      this.contextMenu.visible
    ) {
      return;
    }
  
    this.batchTooltip.visible = true;
    this.batchTooltip.batch = batch;
    this.batchTooltip.x = event.clientX + 14;
    this.batchTooltip.y = event.clientY + 14;
  }

  onGanttWheel(event: WheelEvent): void {

    if (!(event.ctrlKey || event.metaKey)) {
      return;
    }
  
    event.preventDefault();
  
    const board = this.ganttBoard.nativeElement;
  
    const rect = board.getBoundingClientRect();
  
    const mouseX =
        event.clientX - rect.left;
  
    const scrollLeft =
        board.scrollLeft;
  
    const worldX =
        scrollLeft + mouseX;
  
    const oldPixels =
        this.pixelsPerHour;
  
    if (event.deltaY < 0) {
  
        this.pixelsPerHour =
            Math.min(
                this.pixelsPerHour + 2,
                80
            );
  
    } else {
  
        this.pixelsPerHour =
            Math.max(
                this.pixelsPerHour - 2,
                6
            );
    }
  
    const scale =
        this.pixelsPerHour / oldPixels;
  
    board.scrollLeft =
        worldX * scale - mouseX;
  }
  

  moveBatchTooltip(event: MouseEvent): void {  
    if (
      !this.batchTooltip.visible ||
      this.dragService.isBatchDragging() ||
      this.batchContextMenu.visible ||
      this.contextMenu.visible
    ) {
      return;
    }
  
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

    const scenarioId =
      (event.target as HTMLSelectElement).value;
  
    this.selectedScenarioId =
      scenarioId;
  
    /*
     * Try to activate an existing schedule result.
     */
    this.scenarioService.setActiveScenario(
      scenarioId
    );
  
    const selected =
      this.scenarioService.activeScenario();
  
    /*
     * Scenario already has a schedule result.
     */
    if (
      selected &&
      selected.ScenarioID === scenarioId
    ) {
      this.loadScenarioIntoView(
        selected
      );
  
      return;
    }
  
    /*
     * Scenario exists as a definition but has
     * not been optimized yet.
     *
     * Keep it selected for Run Optimizer,
     * but don't display another scenario's result.
     */
    this.activeScenario = null;
  
    this.gantt = [];
    this.plannedTasks = [];
    this.schedule = [];
    this.workOrderSequence = [];
  
    this.kpis = {
      feasible: '-',
      deliveryPerformance: '-',
      lateOrders: '-',
      overSoak: '-',
      ovenUtilization: '-',
      totalCost: '-'
    };
  
    this.clearSelection();
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

    this.ganttService.clearBatchCache();

    this.gantt = this.plannedTasks.map((row: any) => ({
      ...row,
      AssignedMachine: row.PlannedMachine || row.AssignedMachine,
      StartTime: row.StartTime,
      EndTime: row.EndTime,
      lane: row.lane || 0
    }));

    this.captureTimelineRange();

    this.workOrderSequence =
      this.manualChangeService
        .buildWorkOrderSequence(
          this.gantt
        );


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

  captureTimelineRange(): void {
    if (!this.gantt.length) {
      this.timelineMinTime = Date.now();
      this.timelineMaxTime =
        this.timelineMinTime + 24 * 60 * 60 * 1000;
      return;
    }
  
    const actualMin =
      this.timelineService.getMinTime(this.gantt);
  
    const actualMax =
      this.timelineService.getMaxTime(this.gantt);
  
    const padding =
      4 * 60 * 60 * 1000;
  
    this.timelineMinTime =
      actualMin - padding;
  
    this.timelineMaxTime =
      actualMax + padding;
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

        this.activeScenario =
            this.scenarioService.activeScenario();

        this.workOrderSequence = response.workOrderSequence || [];
        this.schedule = response.schedule || [];
        this.plannedTasks = response.plannedTasks || [];

        this.ganttService.clearBatchCache();

        this.gantt = this.plannedTasks.map((row: any) => ({
          ...row,
          AssignedMachine: row.PlannedMachine || row.AssignedMachine,
          StartTime: row.StartTime,
          EndTime: row.EndTime,
          lane: 0
        }));

        this.captureTimelineRange();

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

  getBatchSetupStart(batch: any): string | null {
    const op = batch?.Operations?.[0];
  
    return (
      batch?.SetupStartTime ||
      batch?.SetupStart ||
      op?.SetupStartTime ||
      op?.SetupStart ||
      null
    );
  }
  
  getBatchSetupLeft(batch: any): number {
    const setupStartValue =
      this.getBatchSetupStart(batch);
  
    if (!setupStartValue) {
      return this.getBatchLeft(batch);
    }
  
    const setupStart =
      new Date(setupStartValue).getTime();
  
    const min =
      this.getMinTime();
  
    return (
      ((setupStart - min) /
        (1000 * 60 * 60)) *
      this.pixelsPerHour
    );
  }
  
  getBatchSetupWidth(batch: any): number {
    const setupStartValue =
      this.getBatchSetupStart(batch);
  
    if (
      !setupStartValue ||
      !batch?.StartTime
    ) {
      return 0;
    }
  
    const setupStart =
      new Date(setupStartValue).getTime();
  
    const batchStart =
      new Date(batch.StartTime).getTime();
  
    return Math.max(
      0,
      ((batchStart - setupStart) /
        (1000 * 60 * 60)) *
        this.pixelsPerHour
    );
  }
  
  getBatchSetupMinutes(batch: any): number {
    const setupStartValue =
      this.getBatchSetupStart(batch);
  
    if (
      !setupStartValue ||
      !batch?.StartTime
    ) {
      return 0;
    }
  
    const setupStart =
      new Date(setupStartValue).getTime();
  
    const batchStart =
      new Date(batch.StartTime).getTime();
  
    return Math.max(
      0,
      Math.round(
        (batchStart - setupStart) /
        (1000 * 60)
      )
    );
  }
  
  getBatchWidth(batch: any): number {
    if (!batch?.StartTime || !batch?.BatchEndTime) {
      return 0;
    }
  
    const start = new Date(batch.StartTime).getTime();
    const batchEnd = new Date(batch.BatchEndTime).getTime();
  
    return Math.max(
      1,
      ((batchEnd - start) / (1000 * 60 * 60)) *
        this.pixelsPerHour
    );
  }

  isManualBatch(batch: any): boolean {
    return (batch?.Operations || []).some(
      (op: any) =>
        op.IsManual === true ||
        String(op.Source || '').toUpperCase() === 'MANUAL'
    );
  }

  
  getHeatingWidth(batch: any): number {
    if (!batch?.StartTime || !batch?.HeatingEndTime) {
      return 0;
    }
  
    const start = new Date(batch.StartTime).getTime();
    const heatingEnd = new Date(batch.HeatingEndTime).getTime();
  
    return Math.max(
      0,
      ((heatingEnd - start) / (1000 * 60 * 60)) *
        this.pixelsPerHour
    );
  }

  getOverSoakWidth(batch: any): number {
    if (!batch?.HeatingEndTime || !batch?.BatchEndTime) {
      return 0;
    }
  
    const heatingEnd =
      new Date(batch.HeatingEndTime).getTime();
  
    const batchEnd =
      new Date(batch.BatchEndTime).getTime();
  
    return Math.max(
      0,
      ((batchEnd - heatingEnd) / (1000 * 60 * 60)) *
        this.pixelsPerHour
    );
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
          EndTime: row.EndTime,
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

  getCurrentTimeLeft(): number | null {

    if (!this.gantt.length) {
      return null;
    }
  
    const now = Date.now();
  
    const min = this.getMinTime();
    const max = this.getMaxTime();
  
    if (now < min || now > max) {
      return null;
    }
  
    const hoursFromStart =
      (now - min) / (1000 * 60 * 60);
  
    return hoursFromStart * this.pixelsPerHour;
  }

  getMilestones(): any[] {

    if (!this.plannedTasks.length) {
      return [];
    }
  
    const grouped = new Map<string, any>();
  
    for (const row of this.plannedTasks) {
  
      if (!row.DueDate) {
        continue;
      }
  
      const due = new Date(row.DueDate);
  
      const key = due.toISOString();
  
      if (!grouped.has(key)) {
  
        grouped.set(key, {
          type: 'due',
          dueDate: due,
          workOrders: []
        });
  
      }
  
      grouped.get(key).workOrders.push(row.WorkOrderID);
    }
  
    return [...grouped.values()].map(m => ({
  
      ...m,
  
      left:
        ((m.dueDate.getTime() - this.getMinTime()) /
          (1000 * 60 * 60))
        * this.pixelsPerHour
  
    }));
  }



  getMinTime(): number {
    if (!this.timelineMinTime) {
      this.captureTimelineRange();
    }
  
    return this.timelineMinTime;
  }
  

  getMaxTime(): number {
    if (!this.timelineMaxTime) {
      this.captureTimelineRange();
    }
  
    return this.timelineMaxTime;
  }
  

  getTimelineWidth(): number {
    const totalHours =
      (this.getMaxTime() - this.getMinTime()) /
      (1000 * 60 * 60);
  
    return Math.max(
      totalHours * this.pixelsPerHour,
      2800
    );
  }

  // getHourTicks() {
  //   return this.timelineService.generateHourTicks(
  //     this.gantt,
  //     this.pixelsPerHour
  //   );
  // }

  getHourTicks(): any[] {
    const ticks: any[] = [];
  
    let current =
      new Date(this.getMinTime());
  
    current.setMinutes(0, 0, 0);
  
    while (
      current.getTime() <= this.getMaxTime()
    ) {
      ticks.push({
        label: current.toLocaleTimeString(
          'en-GB',
          {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
          }
        ),
  
        left:
          (
            (
              current.getTime() -
              this.getMinTime()
            ) /
            (1000 * 60 * 60)
          ) *
          this.pixelsPerHour
      });
  
      current = new Date(
        current.getTime() +
        60 * 60 * 1000
      );
    }
  
    return ticks;
  }
  
  // getDayTicks() {
  //   return this.timelineService.generateDayTicks(
  //     this.gantt,
  //     this.pixelsPerHour
  //   );
  // }

  getDayTicks(): any[] {
    const ticks: any[] = [];
  
    let current =
      new Date(this.getMinTime());
  
    current.setHours(0, 0, 0, 0);
  
    while (
      current.getTime() <= this.getMaxTime()
    ) {
      ticks.push({
        label: current.toLocaleDateString(
          'en-GB',
          {
            day: '2-digit',
            month: 'short'
          }
        ),
  
        left:
          (
            (
              current.getTime() -
              this.getMinTime()
            ) /
            (1000 * 60 * 60)
          ) *
          this.pixelsPerHour,
  
        width:
          this.pixelsPerHour * 24
      });
  
      current = new Date(
        current.getTime() +
        24 * 60 * 60 * 1000
      );
    }
  
    return ticks;
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
        const end =
          new Date(
              row.EndTime
          ).getTime();

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

  private getBatchForRow(
    row: any
  ): any | null {
    if (!row?.BatchID) {
      return null;
    }
  
    const machine =
      row.AssignedMachine ||
      row.PlannedMachine;
  
    return (
      this
        .getBatchGroupsForMachine(
          machine
        )
        .find(
          (batch: any) =>
            String(batch.BatchID) ===
            String(row.BatchID)
        ) || null
    );
  }

  private getRenderedOperationElement(
    row: any
  ): HTMLElement | null {
  
    const operationId =
      String(
        row?.OperationID || ''
      ).trim();
  
    if (!operationId) {
      return null;
    }
  
    const elements =
      Array.from(
        document.querySelectorAll<HTMLElement>(
          '[data-operation-id]'
        )
      );
  
    return (
      elements.find(
        element =>
          String(
            element.getAttribute(
              'data-operation-id'
            )
          ).trim() === operationId
      ) || null
    );
  }

  getRowCenterX(
    row: any,
    side: 'start' | 'end'
  ): number {
  
    const element =
      this.getRenderedOperationElement(
        row
      );
  
    const svg =
      document.querySelector(
        '.precedence-layer'
      ) as SVGElement | null;
  
    /*
     * Preferred method:
     * use the actual rendered DOM element.
     */
    if (
      element &&
      svg
    ) {
      const elementRect =
        element.getBoundingClientRect();
  
      const svgRect =
        svg.getBoundingClientRect();
  
      if (side === 'start') {
        return (
          elementRect.left -
          svgRect.left
        );
      }
  
      return (
        elementRect.right -
        svgRect.left
      );
    }
  
    /*
     * Fallback only if DOM element
     * cannot be found.
     */
    const startValue =
      row.StartTime;
  
    const endValue =
      this.isOven(row)
        ? (
            row.ReleaseTime ||
            row.BatchEndTime ||
            row.HeatingEndTime ||
            row.EndTime
          )
        : row.EndTime;
  
    const value =
      side === 'start'
        ? startValue
        : endValue;
  
    if (!value) {
      return 0;
    }
  
    const time =
      new Date(value).getTime();
  
    return (
      (
        time -
        this.getMinTime()
      ) /
      (1000 * 60 * 60)
    ) * this.pixelsPerHour;
  }

  getRowCenterY(
    row: any
  ): number {
  
    const element =
      this.getRenderedOperationElement(
        row
      );
  
    const svg =
      document.querySelector(
        '.precedence-layer'
      ) as SVGElement | null;
  
    /*
     * Preferred method:
     * anchor directly to the centre of
     * the rendered operation.
     */
    if (
      element &&
      svg
    ) {
      const elementRect =
        element.getBoundingClientRect();
  
      const svgRect =
        svg.getBoundingClientRect();
  
      return (
        elementRect.top -
        svgRect.top +
        elementRect.height / 2
      );
    }
  
    /*
     * Fallback.
     */
    const machine =
      row.AssignedMachine ||
      row.PlannedMachine;
  
    const machineTop =
      this.getMachineTopOffset(
        machine
      );
  
    const rowTop =
      this.getTop(row);
  
    const height =
      this.getBarHeight(row);
  
    return (
      machineTop +
      rowTop +
      height / 2
    );
  }


  private isSameVisibleTask(
    first: any,
    second: any
  ): boolean {
    const firstMachine =
      String(
        first.AssignedMachine ||
        first.PlannedMachine ||
        ''
      );
  
    const secondMachine =
      String(
        second.AssignedMachine ||
        second.PlannedMachine ||
        ''
      );
  
    if (
      this.isOven(first) &&
      this.isOven(second) &&
      first.BatchID &&
      second.BatchID
    ) {
      return (
        firstMachine === secondMachine &&
        String(first.BatchID) ===
          String(second.BatchID)
      );
    }
  
    return (
      String(
        first.PlannedTaskID ||
        first.OperationID
      ) ===
      String(
        second.PlannedTaskID ||
        second.OperationID
      )
    );
  }

  private getVisibleTaskKey(
    row: any
  ): string {
    const machine =
      String(
        row.AssignedMachine ||
        row.PlannedMachine ||
        ''
      );
  
    if (
      this.isOven(row) &&
      row.BatchID
    ) {
      return (
        `BATCH|${machine}|` +
        `${String(row.BatchID)}`
      );
    }
  
    return (
      `TASK|` +
      `${String(
        row.PlannedTaskID ||
        row.OperationID
      )}`
    );
  }

  getPrecedenceLinks(): any[] {
    const links: any[] = [];
  
    const rowsByWorkOrder =
      new Map<string, any[]>();
  
    for (const row of this.gantt) {
      const workOrderId =
        String(row.WorkOrderID);
  
      if (!rowsByWorkOrder.has(workOrderId)) {
        rowsByWorkOrder.set(
          workOrderId,
          []
        );
      }
  
      rowsByWorkOrder
        .get(workOrderId)!
        .push(row);
    }
  
    for (
      const [
        workOrderId,
        workOrderRows
      ] of rowsByWorkOrder
    ) {
      const sortedRows =
        [...workOrderRows].sort(
          (a: any, b: any) =>
            Number(a.SequenceNumber || 0) -
            Number(b.SequenceNumber || 0)
        );
  
      /*
       * Collapse raw rows that point to the same
       * visible Gantt object.
       *
       * Oven rows in the same batch become one
       * visible node. Normal press/task rows remain
       * separate nodes.
       */

      const visibleRows =
        [...sortedRows];

  
      for (
        let index = 0;
        index < visibleRows.length - 1;
        index++
      ) {
        const from =
          visibleRows[index];
  
        const to =
          visibleRows[index + 1];
  
        /*
         * Do not draw a link from a visual object
         * back to itself.
         */
        if (
          this.isSameVisibleTask(
            from,
            to
          )
        ) {
          continue;
        }

  
        links.push({
          workOrderId,
  
          fromTaskId:
            from.PlannedTaskID,
  
          toTaskId:
            to.PlannedTaskID,

          fromVisibleKey:
            this.getVisibleTaskKey(from),
          
          toVisibleKey:
            this.getVisibleTaskKey(to),
  
          x1:
            this.getRowCenterX(
              from,
              'end'
            ),
  
          y1:
            this.getRowCenterY(
              from
            ),
  
          x2:
            this.getRowCenterX(
              to,
              'start'
            ),
  
          y2:
            this.getRowCenterY(
              to
            )
        });
      }
    }
  
    return links;
  }

  getPrecedenceTopOffset(): number {
    const header =
      document.querySelector(
        '.timeline-header'
      ) as HTMLElement | null;
  
    if (!header) {
      return 96;
    }
  
    return header.offsetHeight;
  }

  getVisiblePrecedenceLinks(): any[] {
    const links =
      this.getPrecedenceLinks();
  
    /*
     * Whole batch selected:
     * retain current batch behaviour.
     */
    if (this.selectedBatch) {
      const batchKey =
        this.getVisibleTaskKey({
          ...(
            this.selectedBatch
              .Operations?.[0] || {}
          ),
  
          BatchID:
            this.selectedBatch.BatchID,
  
          AssignedMachine:
            this.selectedBatch
              .AssignedMachine
        });
  
      return links.filter(
        link =>
          link.fromVisibleKey ===
            batchKey ||
          link.toVisibleKey ===
            batchKey
      );
    }
  
    /*
     * WO / operation selected:
     *
     * Show ALL precedence links belonging
     * to this work order.
     */
    if (this.selectedRow) {
      const workOrderId =
        String(
          this.selectedRow.WorkOrderID
        );
  
      return links.filter(
        link =>
          String(
            link.workOrderId
          ) === workOrderId
      );
    }
  
    /*
     * Work-order selection fallback:
     * also show complete chain.
     */
    if (this.selectedWorkOrderId) {
      return links.filter(
        link =>
          String(link.workOrderId) ===
          String(
            this.selectedWorkOrderId
          )
      );
    }
  
    return [];
  }


  getArrowPath(
    link: any
  ): string {
    const x1 = link.x1;
    const y1 = link.y1;
    const x2 = link.x2;
    const y2 = link.y2;
  
    const dx =
      x2 - x1;
  
    /*
     * Forward precedence:
     * source is left of target.
     */
    if (dx >= 0) {
      const controlOffset =
        Math.max(
          40,
          Math.abs(dx) * 0.45
        );
  
      return `
        M ${x1} ${y1}
        C ${x1 + controlOffset} ${y1},
          ${x2 - controlOffset} ${y2},
          ${x2} ${y2}
      `;
    }
  
    /*
     * Backward-looking precedence.
     *
     * This happens because the downstream Press
     * operation can visually start before the end
     * of the large oven batch.
     *
     * Do NOT create a huge right-side rectangle.
     * Use a controlled curve instead.
     */
    const controlOffset =
      Math.max(
        45,
        Math.min(
          100,
          Math.abs(dx) * 0.35
        )
      );
  
    return `
      M ${x1} ${y1}
      C ${x1 + controlOffset} ${y1},
        ${x2 + controlOffset} ${y2},
        ${x2} ${y2}
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

    this.selectedBatch = null;
  
    this.selectedRow =
      this.gantt.find(
        row =>
          String(row.WorkOrderID).trim() === workOrderId
      ) || null;
  

    this.contextMenu.visible = false;
  }

  selectBatch(
    event: MouseEvent,
    batch: any
  ): void {
    event.preventDefault();
    event.stopPropagation();
  
    const sameBatch =
      String(this.selectedBatch?.BatchID) ===
      String(batch?.BatchID) &&
      String(
        this.selectedBatch?.AssignedMachine
      ) ===
      String(batch?.AssignedMachine);
  
    if (sameBatch) {
      this.clearSelection();
      return;
    }
  
    this.selectedBatch =
      batch;
  
    this.selectedWorkOrderId =
      null;
  
    this.selectedRow =
      null;
  
    this.contextMenu.visible =
      false;
  
    this.batchContextMenu.visible =
      false;
  }

  selectOperation(
    event: MouseEvent,
    row: any
  ): void {
    event.preventDefault();
    event.stopPropagation();
  
    const sameTask =
      String(
        this.selectedRow?.PlannedTaskID
      ) ===
      String(row?.PlannedTaskID);
  
    if (sameTask) {
      this.clearSelection();
      return;
    }
  
    this.selectedRow =
      row;
  
    this.selectedBatch =
      null;
  
    this.selectedWorkOrderId =
      String(row.WorkOrderID);
  
    this.contextMenu.visible =
      false;
  
    this.batchContextMenu.visible =
      false;
  }
  

  openContextMenu(
    event: MouseEvent,
    row: any
  ): void {
    event.preventDefault();
    event.stopPropagation();
  
    this.hideBatchTooltip();
    this.batchContextMenu.visible = false;
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


  isRowBeingDragged(row: any): boolean {
    return this.dragService.getSnapshot()?.row === row;
  }

  startDrag(event: MouseEvent, row: any): void {
    if (event.button !== 0) {
      return;
    }
  
    if (!this.activeScenario?.IsManualScenario) {
      return;
    }
  
    event.preventDefault();
    event.stopPropagation();
  
    this.selectedRow = row;
    this.contextMenu.visible = false;
    this.batchContextMenu.visible = false;
    this.hideBatchTooltip();
    this.resetDragTarget();
  
    this.dragService.start(event, row);

    this.dragValidation = {
      valid: true,
      message: 'Valid position'
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
    this.dragService.restore();
    this.recalculateLanes();
  }

  undoLastChange(): void {
    const currentScenario =
      this.scenarioService.activeScenario();
  
    if (!currentScenario) {
      alert('No active scenario found.');
      return;
    }
  
    const scenarioId =
      currentScenario.ScenarioID;

      const undoResult =
      this.manualChangeService
        .undoLastChange(
          currentScenario,
          this.gantt
        );
    
    if (!undoResult.success) {
      alert(
        undoResult.message
      );
    
      return;
    }
    
    this.gantt =
      undoResult.gantt;
    /*
     * Remove the restored change from history.
     */
    this.scenarioService
      .removeLastManualChange(
        scenarioId
      );
  
    /*
     * Clear cached batch wrappers because batch
     * times or machines may have changed.
     */
    this.ganttService
      .clearBatchCache();
  
    /*
     * Force Angular to receive new array references.
     */
    this.gantt = [
      ...this.gantt
    ];
  
    this.recalculateLanes();
  
    /*
     * Rebuild planned-task and schedule arrays.
     */
    this.synchronizeScheduleData();

    this.workOrderSequence =
      this.manualChangeService
        .buildWorkOrderSequence(
          this.gantt
        );
    
    /*
     * Update the scenario stored in the service.
     */
    this.scenarioService
      .updateScenarioTasks(
        scenarioId,
        this.plannedTasks
      );
  
    /*
     * Refresh the local active-scenario reference.
     */
    this.activeScenario =
      this.scenarioService
        .activeScenario();
  
    /*
     * Save the restored schedule and shortened
     * manual-change history.
     */
    this.scenarioService
      .saveScenarioToBackend(
        scenarioId
      );
  
    alert(
      'Last manual change undone.'
    );
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

  getAvailableOvensForBatch(
    batch: any
  ): string[] {
    const currentMachine =
      batch?.AssignedMachine ||
      batch?.MachineID ||
      batch?.Machine;
  
    return this.getMachines().filter(
      machine =>
        machine !== currentMachine &&
        this.isOven(machine)
    );
  }

  changeBatchMachine(
    batch: any,
    newMachine: string
  ): void {
    if (
      !batch ||
      !newMachine ||
      !this.activeScenario
    ) {
      return;
    }
  
    const operations =
      batch.Operations || [];
  
    if (!operations.length) {
      return;
    }
  
    const oldMachine =
      operations[0].AssignedMachine ||
      operations[0].PlannedMachine;
  
    for (const row of operations) {
      row.AssignedMachine = newMachine;
      row.PlannedMachine = newMachine;
      row.IsManual = true;
      row.Source = 'MANUAL';
    }
  
    const conflictingRow =
      operations.find((row: any) =>
        this.doesTaskOverlapDowntime(row)
      );
  
    if (conflictingRow) {
      for (const row of operations) {
        row.AssignedMachine = oldMachine;
        row.PlannedMachine = oldMachine;
      }
  
      alert(
        `Batch cannot be moved to ${newMachine} ` +
        `because it overlaps downtime.`
      );
  
      this.recalculateLanes();
      return;
    }
  
    this.synchronizeScheduleData();
  
    this.scenarioService.updateScenarioTasks(
      this.activeScenario.ScenarioID,
      this.plannedTasks
    );
  
    this.scenarioService.addManualChange(
      this.activeScenario.ScenarioID,
      {
        ChangeType: 'BATCH_MACHINE_CHANGE',
        BatchID: batch.BatchID,
        OldValue: {
          Machine: oldMachine
        },
        NewValue: {
          Machine: newMachine
        },
        Note:
          `Planner moved batch ${batch.BatchID} ` +
          `from ${oldMachine} to ${newMachine}.`
      }
    );
  
    this.scenarioService.saveScenarioToBackend(
      this.activeScenario.ScenarioID
    );
  
    this.batchContextMenu.visible = false;
    this.recalculateLanes();
  }

  unplanBatch(): void {
    const batch =
      this.batchContextMenu.batch;
  
    if (!batch || !this.activeScenario) {
      return;
    }
  
    const batchId = batch.BatchID;
  
    const removedRows =
      this.gantt.filter(
        row => row.BatchID === batchId
      );
  
    this.gantt =
      this.gantt.filter(
        row => row.BatchID !== batchId
      );
  
    this.synchronizeScheduleData();
  
    this.scenarioService.updateScenarioTasks(
      this.activeScenario.ScenarioID,
      this.plannedTasks
    );
  
    this.scenarioService.addManualChange(
      this.activeScenario.ScenarioID,
      {
        ChangeType: 'BATCH_UNPLAN',
        BatchID: batchId,
        OldValue:
          structuredClone(removedRows),
        NewValue: null,
        Note:
          `Planner manually unplanned batch ${batchId}.`
      }
    );
  
    this.scenarioService.saveScenarioToBackend(
      this.activeScenario.ScenarioID
    );
  
    this.batchContextMenu.visible = false;
    this.recalculateLanes();
  }

  getMachineAtPointer(
    event: MouseEvent
  ): string | null {
    const elements = document.elementsFromPoint(
      event.clientX,
      event.clientY
    ) as HTMLElement[];
  
    for (const element of elements) {
      const machineElement =
        element.closest<HTMLElement>(
          '[data-gantt-machine]'
        );
  
      const machine =
        machineElement?.dataset['ganttMachine'];
  
      if (machine) {
        return machine;
      }
    }
  
    return null;
  }

  doesTaskOverlapDowntimeOnMachine(
    row: any,
    machine: string
  ): boolean {
    return this.schedulingEngine
      .doesTaskOverlapDowntimeOnMachine(
        row,
        machine,
        this.getDowntimesForMachine(
          machine
        )
      );
  }


  private pushBatchesForwardTransaction(
    batchDrag: any,
    targetMachine: string
  ): BatchPushResult {
    return this.schedulingEngine
      .pushBatchesForwardTransaction({
        batchDrag,
        targetMachine,
        gantt: this.gantt,
  
        targetBatches:
          this.getBatchGroupsForMachine(
            targetMachine
          ),
  
        downtimes:
          this.getDowntimesForMachine(
            targetMachine
          )
      });
  }


  doesBatchOverlapOnMachine(
    batchDrag: any,
    machine: string
  ): boolean {
    return this.schedulingEngine
      .doesBatchOverlapOnMachine(
        batchDrag,
        this.getBatchGroupsForMachine(
          machine
        )
      );
  }
  
  evaluateRowDragTarget(
    event: MouseEvent,
    row: any
  ): void {
    const machine =
      this.getMachineAtPointer(event);
  
    if (!machine) {
      this.dragTarget = {
        machine: null,
        valid: false,
        message: 'Move over a machine row'
      };
  
      return;
    }
  
    if (!this.canMoveRowToMachine(row, machine)) {
      this.dragTarget = {
        machine,
        valid: false,
        message:
          `Operation cannot run on ${machine}`
      };
  
      return;
    }
  
    const downtimeConflict =
      this.doesTaskOverlapDowntimeOnMachine(
        row,
        machine
      );
  
    this.dragTarget = downtimeConflict
      ? {
          machine,
          valid: false,
          message:
            `Downtime conflict on ${machine}`
        }
      : {
          machine,
          valid: true,
          message:
            `Drop on ${machine}`
        };
  }

  evaluateBatchDragTarget(
    event: MouseEvent,
    batchDrag: any
  ): void {
    const machine =
      this.getMachineAtPointer(event);
  
    if (!machine) {
      this.dragTarget = {
        machine: null,
        valid: false,
        message:
          'Move over an oven row'
      };
  
      return;
    }
  
    if (!this.isOven(machine)) {
      this.dragTarget = {
        machine,
        valid: false,
        message:
          `Batch cannot run on ${machine}`
      };
  
      return;
    }
  
    const conflictingRow =
      batchDrag.rows
        .map(
          (item: any) =>
            item.row
        )
        .find(
          (row: any) =>
            this.doesTaskOverlapDowntimeOnMachine(
              row,
              machine
            )
        );
  
    if (conflictingRow) {
      this.dragTarget = {
        machine,
        valid: false,
        message:
          `Downtime conflict on ${machine}`
      };
  
      return;
    }
  
    const overlapsBatch =
      this.doesBatchOverlapOnMachine(
        batchDrag,
        machine
      );
  
    this.dragTarget = {
      machine,
      valid: true,
      message: overlapsBatch
        ? `Drop and push later batches on ${machine}`
        : `Drop batch on ${machine}`
    };
  
    /*
     * Live cross-oven preview.
     */
    for (const item of batchDrag.rows) {
      item.row.AssignedMachine =
        machine;
  
      item.row.PlannedMachine =
        machine;
    }
  
    batchDrag.batch.AssignedMachine =
      machine;
  }
  
  trackBatch(
    index: number,
    batch: any
  ): string {
    return String(
      batch?.AssignedMachine || ''
    ) + '_' + String(batch?.BatchID || index);
  }

  private autoScrollWhileDragging(
      event: MouseEvent
  ): void {

      if (!this.ganttBoard) {
          return;
      }

      const board =
          this.ganttBoard.nativeElement;

      const rect =
          board.getBoundingClientRect();

      const edge = 80;
      const speed = 20;

      if (
          event.clientX <
          rect.left + edge
      ) {
          board.scrollLeft -= speed;
      }

      if (
          event.clientX >
          rect.right - edge
      ) {
          board.scrollLeft += speed;
      }
  }

  @HostListener('document:mousemove', ['$event'])
  onMouseMove(event: MouseEvent): void {
    if (this.dragService.isBatchDragging()) {
      const batchDrag =
        this.dragService.getBatchSnapshot();

      if (!batchDrag) {
        return;
      }

      const changed =
        this.dragService.moveBatch(
          event.clientX,
          event.clientY,
          this.pixelsPerHour
        );

        this.autoScrollWhileDragging(event);

      if (!changed) {
        return;
      }

      this.evaluateBatchDragTarget(
        event,
        batchDrag
      );

      this.dragValidation = {
        valid: this.dragTarget.valid,
        message: this.dragTarget.message
      };

      this.recalculateLanes();
      return;
    }

    const changed =
      this.dragService.move(
        event.clientX,
        event.clientY,
        this.pixelsPerHour
      );

      this.autoScrollWhileDragging(event);

    if (!changed) {
      return;
    }

    const drag =
      this.dragService.getSnapshot();

    if (!drag) {
      return;
    }

    this.evaluateRowDragTarget(
      event,
      drag.row
    );

    this.dragValidation = {
      valid: this.dragTarget.valid,
      message: this.dragTarget.message
    };

    this.recalculateLanes();
  }


  
  @HostListener('window:wheel' , ['$event'])
  preventBrowserZoom(event: WheelEvent) {

      if (event.ctrlKey || event.metaKey) {

          event.preventDefault();

      }

  }

  resetDragValidation(): void {
    this.dragValidation = {
      valid: true,
      message: ''
    };
  }

  resetDragTarget(): void {
    this.dragTarget = {
      machine: null,
      valid: true,
      message: ''
    };
  }
  
  synchronizeScheduleData(): void {
    this.plannedTasks = this.gantt.map(
      task => ({
        ...task,
        PlannedMachine:
          task.AssignedMachine ||
          task.PlannedMachine
      })
    );
  
    this.schedule = this.gantt.map(
      task => ({
        WorkOrderID: task.WorkOrderID,
        OperationID: task.OperationID,
        BatchID: task.BatchID,
        AssignedMachine:
          task.AssignedMachine ||
          task.PlannedMachine,
        StartTime: task.StartTime,
        EndTime: task.EndTime,
        BatchEndTime:
          task.BatchEndTime || null,
        Late:
          task.ViolationReasons?.includes(
            'LATE'
          ) || false,
        OverSoakViolation:
          task.ViolationReasons?.includes(
            'OVER_SOAK'
          ) || false
      })
    );
  }

  private validateBatchMove(
    batchDrag: any
  ): boolean {
  
    if (!batchDrag.moved) {
      this.dragService.cancelBatch();
      this.resetDragTarget();
      this.resetDragValidation();
      return false;
    }
  
    if (!this.activeScenario) {
      this.dragService.restoreBatch();
      this.dragService.cancelBatch();
      this.resetDragValidation();
      return false;
    }
  
    if (
      !this.dragTarget.machine ||
      !this.dragTarget.valid
    ) {
      alert(
        this.dragTarget.message ||
        'Invalid batch drop position.'
      );
  
      this.dragService.restoreBatch();
      this.dragService.cancelBatch();
      this.recalculateLanes();
      this.resetDragTarget();
      this.resetDragValidation();
  
      return false;
    }
  
    return true;
  }

  private executeBatchMove(
    batchDrag: any
  ): {
    success: boolean;
    pushResult?: BatchPushResult;
  } {

    const targetMachine =
      this.dragTarget.machine;

    if (!targetMachine) {
      return {
        success: false
      };
    }
  
    for (const item of batchDrag.rows) {
  
      item.row.AssignedMachine =
        targetMachine;
  
      item.row.PlannedMachine =
        targetMachine;
    }
  
    batchDrag.batch.AssignedMachine =
      targetMachine;
  
  
    const conflictingRow =
      batchDrag.rows
        .map((item: any) => item.row)
        .find((row: any) =>
          this.doesTaskOverlapDowntime(row)
        );
  
    if (conflictingRow) {
  
      const downtime =
        this.getOverlappingDowntime(
          conflictingRow
        );
  
      alert(
        'Batch move rejected. Batch overlaps downtime on ' +
        `${downtime?.MachineID || conflictingRow.AssignedMachine}.`
      );
  
      this.dragService.restoreBatch();
  
      this.dragService.cancelBatch();
  
      this.recalculateLanes();
  
      this.resetDragTarget();
  
      this.resetDragValidation();
  
      return {
        success: false
      };
    }
  
    const pushResult =
      this.pushBatchesForwardTransaction(
        batchDrag,
        targetMachine
      );
  
    if (!pushResult.success) {
  
      alert(pushResult.message);
  
      this.dragService.restoreBatch();
  
      this.dragService.cancelBatch();
  
      this.recalculateLanes();
  
      this.resetDragTarget();
  
      this.resetDragValidation();
  
      return {
        success: false
      };
    }
  
    for (const item of batchDrag.rows) {
  
      item.row.IsManual = true;
  
      item.row.Source = 'MANUAL';
    }
  
    for (
      const pushedSnapshot of
      pushResult.pushedRows
    ) {
  
      pushedSnapshot.row.IsManual = true;
  
      pushedSnapshot.row.Source = 'MANUAL';
    }
  
    return {
  
      success: true,
  
      pushResult
  
    };
  
  }


  private finalizeBatchMove(
    scenarioId: string
  ): void {
  
    this.activeScenario =
      this.scenarioService.activeScenario();
  
    this.scenarioService.saveScenarioToBackend(
      scenarioId
    );
  
    this.gantt = [
      ...this.gantt
    ];
  
    this.plannedTasks = [
      ...this.gantt
    ];
  
    this.dragService.finishBatch();
  
    this.resetDragTarget();
  
    this.recalculateLanes();
  
    this.resetDragValidation();
  }

  finishBatchDrag(batchDrag: any): void {
    if (
        !this.validateBatchMove(
            batchDrag
        )
    ) {
        return;
    }
    
    const scenarioId =
        this.activeScenario!.ScenarioID;

    const execution =
        this.executeBatchMove(
            batchDrag
        );
    
    if (!execution.success) {
        return;
    }
    
    const pushResult =
        execution.pushResult!;
    
    this.synchronizeScheduleData();
  
    this.scenarioService.updateScenarioTasks(
      scenarioId,
      this.plannedTasks
    );

    this.manualChangeService
      .recordBatchMove({
        scenarioId,
        batchDrag,
        pushResult,

        formatDateTime:
          value =>
            this.dragService
              .formatDateTime(value)
      });


    this.finalizeBatchMove(
      scenarioId
    );
  
  }


  @HostListener('document:mouseup')
  onMouseUp(): void {

    const batchDrag =
      this.dragService.getBatchSnapshot();

    if (batchDrag) {
      this.finishBatchDrag(batchDrag);
      return;
    }

    const drag = this.dragService.getSnapshot();

    if (!drag) {
      return;
    }


    if (!drag.moved) {
      this.dragService.cancel();
      this.resetDragTarget();
      this.resetDragValidation();
      return;
    }

    if (!this.activeScenario) {
      this.restoreDraggedRow();
      this.dragService.cancel();
      return;
    }

    const row = drag.row;

    if (
      !this.dragTarget.machine ||
      !this.dragTarget.valid
    ) {
      alert(
        this.dragTarget.message ||
        'Invalid drop position.'
      );
    
      this.restoreDraggedRow();
      this.dragService.cancel();
      this.resetDragTarget();
      this.resetDragValidation();
      return;
    }
    
    row.AssignedMachine =
      this.dragTarget.machine;
    
    row.PlannedMachine =
      this.dragTarget.machine;

    const overlappingDowntime = this.getOverlappingDowntime(row);

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
      this.dragService.cancel();
      return;
    }

    row.IsManual = true;
    row.Source = 'MANUAL';

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
        ChangeType: 'MOVE',
        PlannedTaskID: row.PlannedTaskID,
        WorkOrderID: row.WorkOrderID,
        OperationID: row.OperationID,
        OldValue: {
          StartTime: this.dragService.formatDateTime(drag.originalStart),
          EndTime: this.dragService.formatDateTime(drag.originalEnd),
          HeatingEndTime: drag.originalHeatingEnd !== null
            ? this.dragService.formatDateTime(drag.originalHeatingEnd)
            : null,
          BatchEndTime: drag.originalBatchEnd !== null
            ? this.dragService.formatDateTime(drag.originalBatchEnd)
            : null,
          ReleaseTime: drag.originalReleaseTime !== null
            ? this.dragService.formatDateTime(drag.originalReleaseTime)
            : null,
          Machine: drag.originalMachine
        },
        NewValue: {
          StartTime: row.StartTime,
          EndTime: row.EndTime,
          HeatingEndTime: row.HeatingEndTime || null,
          BatchEndTime: row.BatchEndTime || null,
          ReleaseTime: row.ReleaseTime || null,
          Machine: row.AssignedMachine
        },
        Note: 'Planner manually moved task.'
      }
    );

    this.scenarioService.saveScenarioToBackend(
      this.activeScenario.ScenarioID
    );

    this.dragService.finish();
    this.dragValidation = {
      valid: true,
      message: ''
    };

    this.recalculateLanes();
  }

  clearSelection(): void {
      this.selectedRow = null;
      this.selectedBatch = null;
      this.selectedWorkOrderId = null;
      this.contextMenu.visible = false;
      this.batchContextMenu.visible = false;
  }

  clearSelectionFromGantt(
    event: MouseEvent
  ): void {
    const target =
      event.target as HTMLElement;
  
    if (
      target.closest(
        '.batch-container'
      ) ||
      target.closest(
        '.gantt-bar'
      ) ||
      target.closest(
        '.batch-operation-button'
      ) ||
      target.closest(
        '.context-menu'
      )
    ) {
      return;
    }
  
    this.clearSelection();
  }

  openBatchContextMenu(
    event: MouseEvent,
    batch: any
  ): void {
    event.preventDefault();
    event.stopPropagation();
  
    if (!this.activeScenario?.IsManualScenario) {
      return;
    }
  
    this.hideBatchTooltip();
    this.contextMenu.visible = false;
  
    this.batchContextMenu = {
      visible: true,
      x: event.clientX,
      y: event.clientY,
      batch
    };
  }

  startBatchDrag(
    event: MouseEvent,
    batch: any
  ): void {

    
    if (event.button !== 0) {
      return;
    }
  
    if (!this.activeScenario?.IsManualScenario) {
      return;
    }
  
    if (!batch?.Operations?.length) {
      return;
    }
  
    event.preventDefault();
    event.stopPropagation();
  
    this.contextMenu.visible = false;
    this.batchContextMenu.visible = false;
    this.hideBatchTooltip();
  
    this.resetDragTarget();
  
    this.dragValidation = {
      valid: true,
      message: 'Move batch over an oven row'
    };
  
    this.dragService.startBatch(
      event,
      batch
    );


  }
  

  isBatchBeingDragged(batch: any): boolean {
    return (
      this.dragService
        .getBatchSnapshot()
        ?.batch
        ?.BatchID === batch?.BatchID
    );
  }



  @HostListener('document:click', ['$event'])
    closeContextMenu(event: MouseEvent): void {
    
        const target = event.target as HTMLElement;
    
        if (target.closest('.batch-tooltip')) {
            return;
        }
    
        this.contextMenu.visible = false;
        this.hideBatchTooltip();
        this.batchContextMenu.visible = false;
    }

  @HostListener('document:scroll')
    onDocumentScroll(): void {
      this.hideBatchTooltip();
    }

}