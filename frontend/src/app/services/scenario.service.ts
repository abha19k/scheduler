import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';

export interface ManualChange {
  ManualChangeID: string;
  ScenarioID: string;
  PlannedTaskID?: string;
  WorkOrderID?: string;
  OperationID?: string;
  ChangeType: 'MOVE' | 'RESIZE' | 'UNPLAN' | 'MACHINE_CHANGE';
  OldValue?: any;
  NewValue?: any;
  ChangedBy?: string;
  ChangedDate: string;
  Note?: string;
}

export interface Scenario {
  ScenarioID: string;
  ScenarioName: string;
  CreatedBy?: string;
  CreatedDate?: string;
  BaseScenarioID?: string | null;
  IsManualScenario?: boolean;
  KPIs?: any;
  PlannedTasks?: any[];
  ManualChanges?: ManualChange[];
}

export interface Downtime {
  DowntimeID: string;
  ScenarioID: string;
  MachineID: string;
  StartTime: string;
  EndTime: string;
  Reason: string;
}

export interface ScenarioDefinition {
  ScenarioID: string;
  ScenarioName: string;
  BaseScenarioID?: string | null;
  Description?: string;
  ParameterOverrides: any;
  CalendarOverrides?: any;
  MachineOverrides?: any;
  ObjectiveOverrides?: any;
  Downtimes?: Downtime[];
}

@Injectable({
  providedIn: 'root'
})
export class ScenarioService {
  private definitionsKey = 'planwise_scenario_definitions';
  private resultsKey = 'planwise_scenario_results';
  private importedDataKey = 'planwise_imported_data';

  constructor(
    private http: HttpClient
  ) {}

  private defaultDefinitions: ScenarioDefinition[] = [
    {
      ScenarioID: 'BASE',
      ScenarioName: 'Base Scenario',
      Description: 'Original imported planning data.',
      BaseScenarioID: null,
      ParameterOverrides: {
        PopulationSize: 100,
        Generations: 20,
        MutationRate: 0.30,
        EliteSize: 10,
        TournamentSize: 3,
        LateOrderPenalty: 1000,
        MaxOverSoakMinutes: 240,
        WidthSetupPerUnit: 10,
        TemperatureSetupPer10DegreeMinutes: 15,
        MaximumAllowedGapBetweenHeatingAndPressHours: 4
      },
      CalendarOverrides: {},
      MachineOverrides: {},
      ObjectiveOverrides: {},
      Downtimes: []
    },
    {
      ScenarioID: 'AGGRESSIVE',
      ScenarioName: 'Aggressive Delivery',
      Description: 'Prioritize delivery performance.',
      BaseScenarioID: 'BASE',
      ParameterOverrides: {
        PopulationSize: 250,
        Generations: 60,
        MutationRate: 0.40,
        EliteSize: 10,
        TournamentSize: 3,
        LateOrderPenalty: 10000,
        MaxOverSoakMinutes: 180,
        WidthSetupPerUnit: 10,
        TemperatureSetupPer10DegreeMinutes: 15,
        MaximumAllowedGapBetweenHeatingAndPressHours: 4
      },
      CalendarOverrides: {},
      MachineOverrides: {},
      ObjectiveOverrides: {
        PrioritizeDelivery: true
      },
      Downtimes: []
    },
    {
      ScenarioID: 'ENERGY',
      ScenarioName: 'Energy Saving',
      Description: 'Reduce oven energy usage.',
      BaseScenarioID: 'BASE',
      ParameterOverrides: {
        PopulationSize: 200,
        Generations: 50,
        MutationRate: 0.35,
        EliteSize: 10,
        TournamentSize: 3,
        LateOrderPenalty: 500,
        MaxOverSoakMinutes: 240,
        WidthSetupPerUnit: 10,
        TemperatureSetupPer10DegreeMinutes: 45,
        MaximumAllowedGapBetweenHeatingAndPressHours: 4
      },
      CalendarOverrides: {},
      MachineOverrides: {},
      ObjectiveOverrides: {
        PrioritizeOvenUtilization: true,
        PrioritizeTemperatureStability: true
      },
      Downtimes: []
    },
    {
      ScenarioID: 'MAINTENANCE',
      ScenarioName: 'Maintenance Shutdown',
      Description: 'Scenario with planned equipment downtime.',
      BaseScenarioID: 'BASE',
      ParameterOverrides: {
        PopulationSize: 200,
        Generations: 50,
        MutationRate: 0.40,
        EliteSize: 10,
        TournamentSize: 3,
        LateOrderPenalty: 2000,
        MaxOverSoakMinutes: 240,
        WidthSetupPerUnit: 10,
        TemperatureSetupPer10DegreeMinutes: 15,
        MaximumAllowedGapBetweenHeatingAndPressHours: 4
      },
      CalendarOverrides: {},
      MachineOverrides: {},
      ObjectiveOverrides: {},
      Downtimes: []
    }
  ];

  scenarioDefinitions = signal<ScenarioDefinition[]>(
    this.loadDefinitions()
  );

  scenarios = signal<Scenario[]>(
    this.loadScenarioResults()
  );

  activeScenario = signal<Scenario | null>(null);

  importedData = signal<any>(
    this.loadImportedData()
  );

  private loadDefinitions(): ScenarioDefinition[] {
    const saved = localStorage.getItem(this.definitionsKey);

    if (!saved) {
      return this.defaultDefinitions;
    }

    try {
      return JSON.parse(saved);
    } catch {
      return this.defaultDefinitions;
    }
  }

  private loadScenarioResults(): Scenario[] {
    const saved = localStorage.getItem(this.resultsKey);

    if (!saved) {
      return [];
    }

    try {
      return JSON.parse(saved);
    } catch {
      return [];
    }
  }

  private loadImportedData(): any {
    const saved = localStorage.getItem(this.importedDataKey);

    if (!saved) {
      return null;
    }

    try {
      return JSON.parse(saved);
    } catch {
      return null;
    }
  }

  private saveDefinitions(): void {
    localStorage.setItem(
      this.definitionsKey,
      JSON.stringify(this.scenarioDefinitions())
    );
  }

  private saveScenarioResults(): void {
    localStorage.setItem(
      this.resultsKey,
      JSON.stringify(this.scenarios())
    );
  }

  setImportedData(data: any): void {
    this.importedData.set(data);

    localStorage.setItem(
      this.importedDataKey,
      JSON.stringify(data)
    );
  }

  saveScenarioDefinitionToBackend(
    definition: ScenarioDefinition
  ): void {
    this.http.post(
      'http://127.0.0.1:8000/api/save-scenario-definition',
      definition
    ).subscribe({
      error: err => {
        console.error(
          'Could not save scenario definition',
          err
        );
      }
    });
  }

  loadScenarioDefinitionsFromBackend(): void {
    this.http.get<any>(
      'http://127.0.0.1:8000/api/scenario-definitions'
    ).subscribe({
      next: response => {
        const definitions: ScenarioDefinition[] =
          response.definitions || [];

        if (!definitions.length) {
          return;
        }

        this.scenarioDefinitions.set(
          definitions.map(definition => ({
            ...definition,
            ParameterOverrides: definition.ParameterOverrides || {},
            CalendarOverrides: definition.CalendarOverrides || {},
            MachineOverrides: definition.MachineOverrides || {},
            ObjectiveOverrides: definition.ObjectiveOverrides || {},
            Downtimes: definition.Downtimes || []
          }))
        );

        this.saveDefinitions();
      },

      error: err => {
        console.error(
          'Could not load scenario definitions',
          err
        );
      }
    });
  }

  loadSavedScenarioResultsFromBackend(): void {
    this.http.get<any>(
      'http://127.0.0.1:8000/api/scenarios'
    ).subscribe({
      next: response => {
        const backendScenarios: Scenario[] =
          response.scenarios || [];

        if (!backendScenarios.length) {
          return;
        }

        const normalizedScenarios = backendScenarios.map(scenario => ({
          ...scenario,
          PlannedTasks: scenario.PlannedTasks || [],
          ManualChanges: scenario.ManualChanges || []
        }));

        this.scenarios.set(normalizedScenarios);
        this.saveScenarioResults();

        if (!this.activeScenario() && normalizedScenarios.length) {
          this.activeScenario.set(normalizedScenarios[0]);
        }
      },

      error: err => {
        console.error(
          'Could not load saved scenarios from backend',
          err
        );
      }
    });
  }

  getScenarioDefinition(
    scenarioId: string
  ): ScenarioDefinition | undefined {
    return this.scenarioDefinitions().find(
      scenario => scenario.ScenarioID === scenarioId
    );
  }

  upsertScenarioDefinition(
    definition: ScenarioDefinition
  ): void {
    const normalized: ScenarioDefinition = {
      ...definition,
      ParameterOverrides: definition.ParameterOverrides || {},
      CalendarOverrides: definition.CalendarOverrides || {},
      MachineOverrides: definition.MachineOverrides || {},
      ObjectiveOverrides: definition.ObjectiveOverrides || {},
      Downtimes: definition.Downtimes || []
    };

    const exists = this.scenarioDefinitions().some(
      s => s.ScenarioID === normalized.ScenarioID
    );

    if (exists) {
      this.scenarioDefinitions.update(list =>
        list.map(s =>
          s.ScenarioID === normalized.ScenarioID
            ? normalized
            : s
        )
      );
    } else {
      this.scenarioDefinitions.update(list => [
        ...list,
        normalized
      ]);
    }

    this.saveDefinitions();
  }

  createScenarioDefinitionFromBase(
    baseScenarioId: string,
    newScenarioName: string
  ): ScenarioDefinition {
    const base = this.getScenarioDefinition(baseScenarioId);

    const newScenarioId =
      'SCN_' +
      newScenarioName
        .trim()
        .toUpperCase()
        .replace(/[^A-Z0-9]+/g, '_') +
      '_' +
      Date.now();

    const definition: ScenarioDefinition = {
      ...(base ? structuredClone(base) : {
        ParameterOverrides: {},
        CalendarOverrides: {},
        MachineOverrides: {},
        ObjectiveOverrides: {},
        Downtimes: []
      }),

      ScenarioID: newScenarioId,
      ScenarioName: newScenarioName,
      BaseScenarioID: baseScenarioId,
      Description: `Created from ${baseScenarioId}`,
      Downtimes: []
    };

    this.upsertScenarioDefinition(definition);
    this.saveScenarioDefinitionToBackend(definition);

    return definition;
  }

  updateScenarioParameters(
    scenarioId: string,
    parameterOverrides: any
  ): void {
    this.scenarioDefinitions.update(list =>
      list.map(s => {
        if (s.ScenarioID !== scenarioId) {
          return s;
        }

        return {
          ...s,
          ParameterOverrides: {
            ...s.ParameterOverrides,
            ...parameterOverrides
          }
        };
      })
    );

    this.saveDefinitions();

    const updated = this.getScenarioDefinition(scenarioId);

    if (updated) {
      this.saveScenarioDefinitionToBackend(updated);
    }
  }

  addDowntime(
    scenarioId: string,
    downtime: Omit<Downtime, 'DowntimeID' | 'ScenarioID'>
  ): void {
    const newDowntime: Downtime = {
      DowntimeID: `DT_${Date.now()}`,
      ScenarioID: scenarioId,
      ...downtime
    };

    this.scenarioDefinitions.update(list =>
      list.map(s => {
        if (s.ScenarioID !== scenarioId) {
          return s;
        }

        return {
          ...s,
          Downtimes: [
            ...(s.Downtimes || []),
            newDowntime
          ]
        };
      })
    );

    this.saveDefinitions();

    const updated = this.getScenarioDefinition(scenarioId);

    if (updated) {
      this.saveScenarioDefinitionToBackend(updated);
    }
  }

  removeDowntime(
    scenarioId: string,
    downtimeId: string
  ): void {
    this.scenarioDefinitions.update(list =>
      list.map(s => {
        if (s.ScenarioID !== scenarioId) {
          return s;
        }

        return {
          ...s,
          Downtimes: (s.Downtimes || []).filter(
            d => d.DowntimeID !== downtimeId
          )
        };
      })
    );

    this.saveDefinitions();

    const updated = this.getScenarioDefinition(scenarioId);

    if (updated) {
      this.saveScenarioDefinitionToBackend(updated);
    }
  }

  createScenario(
    scenario: Scenario
  ): void {
    const normalizedScenario: Scenario = {
      ...scenario,
      PlannedTasks: scenario.PlannedTasks || [],
      ManualChanges: scenario.ManualChanges || []
    };

    const exists = this.scenarios().some(
      s => s.ScenarioID === normalizedScenario.ScenarioID
    );

    if (exists) {
      this.scenarios.update(list =>
        list.map(s =>
          s.ScenarioID === normalizedScenario.ScenarioID
            ? normalizedScenario
            : s
        )
      );
    } else {
      this.scenarios.update(list => [
        ...list,
        normalizedScenario
      ]);
    }

    this.activeScenario.set(normalizedScenario);
    this.saveScenarioResults();
  }

  setActiveScenario(
    scenarioId: string
  ): void {
    const found = this.scenarios().find(
      s => s.ScenarioID === scenarioId
    );

    if (found) {
      this.activeScenario.set(found);
    }
  }

  updateScenarioTasks(
    scenarioId: string,
    plannedTasks: any[]
  ): void {
    this.scenarios.update(list =>
      list.map(s => {
        if (s.ScenarioID !== scenarioId) {
          return s;
        }

        return {
          ...s,
          PlannedTasks: plannedTasks
        };
      })
    );

    const active = this.activeScenario();

    if (active && active.ScenarioID === scenarioId) {
      this.activeScenario.update(s => {
        if (!s) {
          return null;
        }

        return {
          ...s,
          PlannedTasks: plannedTasks
        };
      });
    }

    this.saveScenarioResults();
  }

  addManualChange(
    scenarioId: string,
    change: Omit<ManualChange, 'ManualChangeID' | 'ScenarioID' | 'ChangedDate'>
  ): void {
    const manualChange: ManualChange = {
      ManualChangeID: `MC_${Date.now()}`,
      ScenarioID: scenarioId,
      ChangedDate: new Date().toISOString(),
      ChangedBy: 'planner',
      ...change
    };

    this.scenarios.update(list =>
      list.map(s => {
        if (s.ScenarioID !== scenarioId) {
          return s;
        }

        return {
          ...s,
          IsManualScenario: true,
          ManualChanges: [
            ...(s.ManualChanges || []),
            manualChange
          ]
        };
      })
    );

    const active = this.activeScenario();

    if (active && active.ScenarioID === scenarioId) {
      this.activeScenario.update(s => {
        if (!s) {
          return null;
        }

        return {
          ...s,
          IsManualScenario: true,
          ManualChanges: [
            ...(s.ManualChanges || []),
            manualChange
          ]
        };
      });
    }

    this.saveScenarioResults();
  }

  cloneScenario(
    sourceScenarioId: string,
    newScenarioId: string,
    newName: string
  ): void {
    const source = this.scenarios().find(
      s => s.ScenarioID === sourceScenarioId
    );

    if (!source) {
      return;
    }

    const cloned: Scenario = {
      ...structuredClone(source),
      ScenarioID: newScenarioId,
      ScenarioName: newName,
      BaseScenarioID: sourceScenarioId,
      IsManualScenario: true,
      ManualChanges: []
    };

    this.scenarios.update(list => [
      ...list,
      cloned
    ]);

    this.activeScenario.set(cloned);
    this.saveScenarioResults();
  }

  getManualChanges(
    scenarioId: string
  ): ManualChange[] {
    const scenario = this.scenarios().find(
      s => s.ScenarioID === scenarioId
    );

    return scenario?.ManualChanges || [];
  }

  saveScenarioToBackend(
    scenarioId: string
  ): void {
    const scenario = this.scenarios().find(
      s => s.ScenarioID === scenarioId
    );

    if (!scenario) {
      return;
    }

    this.http.post(
      'http://127.0.0.1:8000/api/save-manual-changes',
      {
        scenarioId: scenario.ScenarioID,
        plannedTasks: scenario.PlannedTasks || [],
        manualChanges: scenario.ManualChanges || []
      }
    ).subscribe({
      next: () => {
        console.log(
          'Scenario saved to backend Excel.'
        );
      },

      error: err => {
        console.error(
          'Failed to save scenario',
          err
        );
      }
    });
  }

  clearAllScenarioData(): void {
    localStorage.removeItem(this.definitionsKey);
    localStorage.removeItem(this.resultsKey);
    localStorage.removeItem(this.importedDataKey);

    this.scenarioDefinitions.set(this.defaultDefinitions);
    this.scenarios.set([]);
    this.activeScenario.set(null);
    this.importedData.set(null);
  }

  loadImportedDataFromBackend(): void {
    this.http.get<any>(
      'http://127.0.0.1:8000/api/imported-data'
    ).subscribe({
      next: response => {
        if (!response || !response.sheets) {
          return;
        }
  
        if (!Object.keys(response.sheets).length) {
          return;
        }
  
        this.importedData.set(response);
  
        localStorage.setItem(
          this.importedDataKey,
          JSON.stringify(response)
        );
      },
  
      error: err => {
        console.error(
          'Could not load imported data from backend',
          err
        );
      }
    });
  }

  deleteScenario(
    scenarioId: string
  ): void {
    this.scenarioDefinitions.update(list =>
      list.filter(
        scenario => scenario.ScenarioID !== scenarioId
      )
    );
  
    this.scenarios.update(list =>
      list.filter(
        scenario => scenario.ScenarioID !== scenarioId
      )
    );
  
    const active = this.activeScenario();
  
    if (active?.ScenarioID === scenarioId) {
      this.activeScenario.set(null);
    }
  
    this.saveDefinitions();
    this.saveScenarioResults();
  
    this.http.delete(
      `http://127.0.0.1:8000/api/scenario/${scenarioId}`
    ).subscribe({
      error: err => {
        console.error(
          'Could not delete scenario from backend',
          err
        );
      }
    });
  }
}