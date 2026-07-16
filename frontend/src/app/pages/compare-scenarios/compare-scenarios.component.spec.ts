import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CompareScenariosComponent } from './compare-scenarios.component';

describe('CompareScenariosComponent', () => {
  let component: CompareScenariosComponent;
  let fixture: ComponentFixture<CompareScenariosComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CompareScenariosComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CompareScenariosComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
