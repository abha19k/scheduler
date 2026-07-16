import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink, RouterLinkActive } from '@angular/router';
import {
  HttpClient,
  HttpEventType
} from '@angular/common/http';

import {
  Downtime,
  ScenarioDefinition,
  ScenarioService
} from '../../services/scenario.service';

interface ImportedSheetPreview {
  columns: string[];
  rows: any[];
  previewRows?: any[];
  totalRows: number;
}

@Component({
  selector: 'app-data',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    RouterLinkActive
  ],
  templateUrl: './data.component.html',
  styleUrl: './data.component.scss'
})
export class DataComponent {
  constructor(
    public scenarioService: ScenarioService,
    private http: HttpClient
  ) {}

  selectedScenarioId = 'BASE';

  newScenarioName = '';
  newScenarioBaseId = 'BASE';

  selectedFile: File | null = null;

  uploading = false;
  uploadProgress = 0;

  importedData: any = null;

  pageSize = 25;

  sheetPageIndex: Record<string, number> = {};
  sheetSearchText: Record<string, string> = {};

  ngOnInit(): void {
    this.importedData = this.scenarioService.importedData();
  }

  newDowntime = {
    MachineID: 'Oven1',
    StartTime: '',
    EndTime: '',
    Reason: 'Maintenance'
  };

  machineOptions = [
    'Oven1',
    'Oven2',
    'Oven3',
    'Press1',
    'Press2'
  ];

  getScenarioDefinitions(): ScenarioDefinition[] {
    return this.scenarioService.scenarioDefinitions();
  }

  getSelectedScenario(): ScenarioDefinition | undefined {
    return this.scenarioService.getScenarioDefinition(
      this.selectedScenarioId
    );
  }

  getSelectedParameters(): any {
    return this.getSelectedScenario()?.ParameterOverrides || {};
  }

  getImportedSheetNames(): string[] {
    if (!this.importedData || !this.importedData.sheets) {
      return [];
    }

    return Object.keys(this.importedData.sheets);
  }

  getImportedSheet(sheetName: string): ImportedSheetPreview {
    if (!this.importedData || !this.importedData.sheets) {
      return {
        columns: [],
        rows: [],
        totalRows: 0
      };
    }

    return this.importedData.sheets[sheetName] || {
      columns: [],
      rows: [],
      totalRows: 0
    };
  }

  getRowsForSheet(sheetName: string): any[] {
    const sheet = this.getImportedSheet(sheetName);

    return sheet.rows || [];
  }

  getSearchText(sheetName: string): string {
    return this.sheetSearchText[sheetName] || '';
  }

  updateSearchText(
    sheetName: string,
    value: string
  ): void {
    this.sheetSearchText[sheetName] = value;
    this.sheetPageIndex[sheetName] = 0;
  }

  getFilteredRows(sheetName: string): any[] {
    const rows = this.getRowsForSheet(sheetName);
    const search = this.getSearchText(sheetName).toLowerCase().trim();

    if (!search) {
      return rows;
    }

    return rows.filter(row =>
      Object.values(row).some(value =>
        String(value ?? '').toLowerCase().includes(search)
      )
    );
  }

  getPageIndex(sheetName: string): number {
    return this.sheetPageIndex[sheetName] || 0;
  }

  getTotalPages(sheetName: string): number {
    const totalRows = this.getFilteredRows(sheetName).length;

    return Math.max(
      Math.ceil(totalRows / this.pageSize),
      1
    );
  }

  getPaginatedRows(sheetName: string): any[] {
    const rows = this.getFilteredRows(sheetName);
    const pageIndex = this.getPageIndex(sheetName);

    const start = pageIndex * this.pageSize;
    const end = start + this.pageSize;

    return rows.slice(start, end);
  }

  goToPreviousPage(sheetName: string): void {
    const currentPage = this.getPageIndex(sheetName);

    this.sheetPageIndex[sheetName] = Math.max(
      currentPage - 1,
      0
    );
  }

  goToNextPage(sheetName: string): void {
    const currentPage = this.getPageIndex(sheetName);
    const totalPages = this.getTotalPages(sheetName);

    this.sheetPageIndex[sheetName] = Math.min(
      currentPage + 1,
      totalPages - 1
    );
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;

    if (!input.files || !input.files.length) {
      return;
    }

    this.selectedFile = input.files[0];
  }

  uploadExcel(): void {
    if (!this.selectedFile) {
      alert('Please select an Excel file.');
      return;
    }

    const formData = new FormData();

    formData.append(
      'file',
      this.selectedFile
    );

    formData.append(
      'scenarioId',
      this.selectedScenarioId
    );

    this.uploading = true;
    this.uploadProgress = 0;

    this.http.post<any>(
      'http://127.0.0.1:8000/api/upload-excel',
      formData,
      {
        reportProgress: true,
        observe: 'events'
      }
    ).subscribe({
      next: (event) => {
        if (
          event.type === HttpEventType.UploadProgress &&
          event.total
        ) {
          this.uploadProgress = Math.round(
            100 * event.loaded / event.total
          );
        }

        if (event.type === HttpEventType.Response) {
          this.uploading = false;

          this.importedData = event.body;

          this.sheetPageIndex = {};
          this.sheetSearchText = {};

          this.scenarioService.setImportedData(
            event.body
          );

          alert(
            'Excel uploaded successfully. You can now edit scenarios and run scheduler from the Scheduling page.'
          );
        }
      },

      error: (err) => {
        this.uploading = false;
        console.error(err);
        alert('Upload failed.');
      }
    });
  }

  updateParameter(
    key: string,
    value: string | number
  ): void {
    const numericValue = Number(value);

    this.scenarioService.updateScenarioParameters(
      this.selectedScenarioId,
      {
        [key]: numericValue
      }
    );
  }

  createScenario(): void {
    const scenarioName = this.newScenarioName.trim();

    if (!scenarioName) {
      alert('Please enter a scenario name.');
      return;
    }

    const created = this.scenarioService.createScenarioDefinitionFromBase(
      this.newScenarioBaseId,
      scenarioName
    );

    this.selectedScenarioId = created.ScenarioID;
    this.newScenarioName = '';
  }

  addDowntime(): void {
    if (
      !this.newDowntime.MachineID ||
      !this.newDowntime.StartTime ||
      !this.newDowntime.EndTime
    ) {
      alert('Please enter machine, start time, and end time.');
      return;
    }

    this.scenarioService.addDowntime(
      this.selectedScenarioId,
      {
        MachineID: this.newDowntime.MachineID,
        StartTime: this.newDowntime.StartTime,
        EndTime: this.newDowntime.EndTime,
        Reason: this.newDowntime.Reason || 'Downtime'
      }
    );

    this.newDowntime = {
      MachineID: 'Oven1',
      StartTime: '',
      EndTime: '',
      Reason: 'Maintenance'
    };
  }

  removeDowntime(downtime: Downtime): void {
    this.scenarioService.removeDowntime(
      this.selectedScenarioId,
      downtime.DowntimeID
    );
  }
}