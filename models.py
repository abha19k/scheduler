# models.py

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional, List, Dict, Any


@dataclass
class Operation:
    WorkOrderID: str
    OperationID: str
    SequenceNumber: int
    OperationType: str

    AllowedMachines: List[str]
    DurationHours: float
    DueDate: datetime

    EarliestStart: Optional[datetime] = None

    Width: Optional[float] = None
    Color: Optional[str] = None
    Tool: Optional[str] = None
    ProductFamily: Optional[str] = None

    Weight: Optional[float] = None
    Length: Optional[float] = None
    Temperature: Optional[float] = None

    Priority: int = 1

    AssignedMachine: Optional[str] = None
    BatchID: Optional[str] = None
    PersistentBatchID: Optional[str] = None

    SetupStart: Optional[datetime] = None
    StartTime: Optional[datetime] = None
    EndTime: Optional[datetime] = None

    SetupMinutes: float = 0
    FamilySetupMinutes: float = 0
    WidthSetupMinutes: float = 0
    TemperatureSetupMinutes: float = 0

    OverSoakMinutes: float = 0
    OverSoakViolation: bool = False

    Late: bool = False
    LatePenalty: float = 0


@dataclass
class Machine:
    MachineID: str
    MachineType: str = "Regular"

    ParallelCapacity: int = 1
    Status: str = "Active"

    StartTime: Optional[datetime] = None
    EndTime: Optional[datetime] = None

    MaxWeight: Optional[float] = None
    MaxLength: Optional[float] = None
    MaxTemperature: Optional[float] = None

    CalendarIDs: List[str] = field(default_factory=list)

    Timeline: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CalendarDetail:
    CalendarID: str
    RuleType: str

    AvailableStartTime: Optional[time] = None
    AvailableEndTime: Optional[time] = None

    Weekday: Optional[str] = None
    IsUnavailable: bool = False

    SpecificDate: Optional[datetime] = None
    Reason: Optional[str] = None


@dataclass
class ScenarioDefinition:
    ScenarioID: str
    ScenarioName: str

    BaseScenarioID: Optional[str] = None
    Description: Optional[str] = None

    CalendarOverrides: Dict[str, Any] = field(default_factory=dict)
    RuleOverrides: Dict[str, Any] = field(default_factory=dict)
    ParameterOverrides: Dict[str, Any] = field(default_factory=dict)
    MachineOverrides: Dict[str, Any] = field(default_factory=dict)
    ObjectiveOverrides: Dict[str, Any] = field(default_factory=dict)

    IsBaseScenario: bool = False


@dataclass
class RuleConfiguration:
    RuleConfigID: str
    ScenarioID: str

    RuleName: str
    RuleValue: Any

    RuleDescription: Optional[str] = None
    IsActive: bool = True


@dataclass
class Violation:
    ViolationID: str

    ScenarioID: str
    PlannedTaskID: str

    RuleType: str
    Severity: str
    Message: str

    IsBlocking: bool = False
    CreatedDate: Optional[datetime] = None


@dataclass
class PlannedTask:
    PlannedTaskID: str
    ScenarioID: str

    WorkOrderID: str
    OperationID: str
    SequenceNumber: int

    PlannedMachine: str

    StartTime: datetime
    EndTime: datetime
    DurationHours: float
    BatchEndTime: Optional[datetime] = None

    ProductFamily: Optional[str] = None
    Temperature: Optional[float] = None
    Weight: Optional[float] = None
    Length: Optional[float] = None

    SetupStart: Optional[datetime] = None
    SetupMinutes: float = 0

    BatchID: Optional[str] = None
    PersistentBatchID: Optional[str] = None

    IsManual: bool = False
    IsUnplanned: bool = False

    ViolationStatus: str = "OK"
    ViolationReasons: List[str] = field(default_factory=list)

    Source: str = "GA"

    CreatedDate: Optional[datetime] = None
    UpdatedDate: Optional[datetime] = None


@dataclass
class ManualChange:
    ManualChangeID: str

    ScenarioID: str
    PlannedTaskID: str

    ChangeType: str

    OldValue: Optional[Any] = None
    NewValue: Optional[Any] = None

    ChangedBy: Optional[str] = None
    ChangedDate: Optional[datetime] = None

    Note: Optional[str] = None


@dataclass
class ScenarioKPI:
    ScenarioID: str

    FeasibleSchedule: bool = False

    InfeasibleCount: int = 0
    OverSoakViolations: int = 0

    TotalOperations: int = 0
    LateOperations: int = 0

    DeliveryPerformancePercent: float = 0

    LatePenalty: float = 0

    TotalSetupMinutes: float = 0
    FamilySetupMinutes: float = 0
    WidthSetupMinutes: float = 0
    TemperatureSetupMinutes: float = 0

    OvenUtilizationPercent: float = 0
    MachineUtilizationPercent: float = 0

    ProductionHours: float = 0
    TotalScheduleHours: float = 0

    TotalCost: float = 0


@dataclass
class Scenario:
    ScenarioID: str
    ScenarioName: str

    CreatedBy: Optional[str] = None
    CreatedDate: Optional[datetime] = None

    BaseScenarioID: Optional[str] = None
    IsManualScenario: bool = False

    CalendarID: Optional[str] = None

    RuleConfigurations: List[RuleConfiguration] = field(default_factory=list)
    PlannedTasks: List[PlannedTask] = field(default_factory=list)
    Violations: List[Violation] = field(default_factory=list)
    ManualChanges: List[ManualChange] = field(default_factory=list)

    KPIs: Optional[ScenarioKPI] = None

    PlannerNotes: Optional[str] = None
    Status: str = "Draft"


@dataclass
class Parameters:
    WidthSetupPerUnit: int = 10
    LateOrderPenalty: int = 1000

    PopulationSize: int = 500
    Generations: int = 1000
    MutationRate: float = 0.25
    EliteSize: int = 50
    TournamentSize: int = 3

    TemperatureSetupPer10DegreeMinutes: int = 15
    MaximumAllowedGapBetweenHeatingAndPressHours: float = 4
    MaxOverSoakMinutes: int = 240

    HeatStrategy: str = "JustInTime"

    Objectives: List[str] = field(default_factory=list)

    PlanningStart: Optional[datetime] = None




@dataclass
class SchedulingInput:
    operations: List[Operation]
    machines: Dict[str, Machine]
    family_setup_matrix: Dict[tuple, float]
    parameters: Parameters

    calendar_details: Dict[str, List[CalendarDetail]] = field(default_factory=dict)

    scenario_definitions: Dict[str, ScenarioDefinition] = field(default_factory=dict)
    scenarios: Dict[str, Scenario] = field(default_factory=dict)

    active_scenario_id: Optional[str] = None

    objective_overrides: Dict[str, Any] = field(default_factory=dict)