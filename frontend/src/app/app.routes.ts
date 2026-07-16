import { Routes } from '@angular/router';

import { DataComponent } from './pages/data/data.component';
import { SolutionComponent } from './pages/solution/solution.component';

export const routes: Routes = [
  { path: '', redirectTo: 'data', pathMatch: 'full' },
  { path: 'data', component: DataComponent },
  { path: 'solution', component: SolutionComponent },
  {
    path: 'compare-scenarios',
    loadComponent: () =>
      import('./pages/compare-scenarios/compare-scenarios.component')
        .then(m => m.CompareScenariosComponent)
  }
];