import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink, RouterLinkActive } from '@angular/router';

import {
  Scenario,
  ScenarioService
} from '../../services/scenario.service';

@Component({
  selector: 'app-compare-scenarios',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    RouterLinkActive
  ],
  templateUrl: './compare-scenarios.component.html',
  styleUrl: './compare-scenarios.component.scss'
})
export class CompareScenariosComponent {
  constructor(
    public scenarioService: ScenarioService
  ) {}

  selectedScenarioIds: string[] = [];

  ngOnInit(): void {
    this.scenarioService.loadSavedScenarioResultsFromBackend();
  
    setTimeout(() => {
      const scenarios = this.getScenarios();
  
      const baseScenario = scenarios.find(
        scenario => scenario.ScenarioID === 'BASE'
      );
  
      if (baseScenario) {
        this.selectedScenarioIds = ['BASE'];
        return;
      }
  
      if (scenarios.length) {
        this.selectedScenarioIds = [
          scenarios[0].ScenarioID
        ];
      }
    }, 500);
  }


  getScenarios(): Scenario[] {
    return this.scenarioService.scenarios();
  }

  getSelectedScenarios(): Scenario[] {
    return this.getScenarios().filter(
      scenario => this.selectedScenarioIds.includes(
        scenario.ScenarioID
      )
    );
  }

  toggleScenario(
    scenarioId: string,
    checked: boolean
  ): void {
    if (checked) {
      if (!this.selectedScenarioIds.includes(scenarioId)) {
        this.selectedScenarioIds = [
          ...this.selectedScenarioIds,
          scenarioId
        ];
      }

      return;
    }

    this.selectedScenarioIds =
      this.selectedScenarioIds.filter(
        id => id !== scenarioId
      );
  }

  getKpiValue(
    scenario: Scenario,
    key: string
  ): string | number {
    const value = scenario.KPIs?.[key];

    if (
      value === undefined ||
      value === null ||
      value === ''
    ) {
      return '-';
    }

    return value;
  }

  getScenarioStatusText(): string {
    const count = this.getScenarios().length;

    if (count === 0) {
      return 'No scenario results yet. Run the optimizer from the Scheduling page first.';
    }

    return `${count} scenario result${count === 1 ? '' : 's'} available.`;
  }

  deleteScenario(
    scenarioId: string
  ): void {
    const confirmed = confirm(
      'Are you sure you want to delete this scenario? This will remove its KPIs, planned tasks, and saved result.'
    );
  
    if (!confirmed) {
      return;
    }
  
    this.selectedScenarioIds =
      this.selectedScenarioIds.filter(
        id => id !== scenarioId
      );
  
    this.scenarioService.deleteScenario(
      scenarioId
    );

    if (scenarioId === 'BASE') {
      alert('Base Scenario cannot be deleted.');
      return;
    }
  }
}