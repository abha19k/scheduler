import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { ScenarioService } from './services/scenario.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    RouterOutlet
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent {
  constructor(
    private scenarioService: ScenarioService
  ) {}

  ngOnInit(): void {
    this.scenarioService.loadImportedDataFromBackend();
  
    this.scenarioService.loadScenarioDefinitionsFromBackend();
  
    this.scenarioService.loadSavedScenarioResultsFromBackend();
  }  

}