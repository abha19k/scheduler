
====================================================
1. CORE CONCEPT
====================================================

A Scenario represents:

"A version of the production plan"

Each scenario:
- uses same master data
- uses same work orders
- uses same machines
- BUT can produce different schedules
- Different calenders

Examples:

Scenario A:
- aggressive delivery plan

Scenario B:
- energy-saving plan

Scenario C:
- manual planner-adjusted plan

Scenario D:
- what-if simulation


====================================================
2. DATA MODEL
====================================================


MASTER DATA (GLOBAL / CONSTANT)
----------------------------------------------------

These are shared across ALL scenarios.


Machines
│
├── Oven1
├── Oven2
├── Oven3
├── Press1
└── Press2


WorkOrders
│
├── 1010
├── 1011
├── 1012
└── ...


WorkOrderOperations
│
├── 1010-1
├── 1010-2
├── 1010-3
└── ...


These NEVER change across scenarios.



====================================================
3. SCENARIO-SPECIFIC DATA
====================================================


Scenario
│
├── Calendar
├── PlannedTasks
├── PlannedSequence
├── KPIs
├── Violations
├── ManualChanges
└── PlannerNotes


Each scenario owns its own:
- schedule
- sequence
- KPI results
- violations
- manual changes



====================================================
4. SCENARIO OBJECT
====================================================


Scenario
│
├── ScenarioID
├── ScenarioName
├── CreatedBy
├── CreatedDate
├── BaseScenarioID
├── IsManualScenario
├── CalendarID
├── KPIs
└── PlannedTasks


Example:

Scenario
│
├── ScenarioID = 5
├── ScenarioName = "Manual Planner Version"
├── BaseScenarioID = 1
└── IsManualScenario = True



====================================================
5. PLANNED TASK OBJECT
====================================================


PlannedTask
│
├── PlannedTaskID
├── ScenarioID
├── WorkOrderID
├── OperationID
├── SequenceNumber
├── PlannedMachine
├── StartTime
├── EndTime
├── Duration
├── IsManual
├── ViolationStatus
├── ViolationReasons
└── BatchID


This becomes the MOST IMPORTANT runtime object.


Example:

PlannedTask
│
├── ScenarioID = 5
├── WorkOrderID = 1010
├── OperationID = 1010-1
├── PlannedMachine = Oven1
├── StartTime = 2026-05-18 08:00
├── EndTime = 2026-05-18 22:00
└── IsManual = True



====================================================
6. MANUAL PLANNING FLOW
====================================================


Planner Action
│
├── Drag operation card
├── Drop on machine timeline
└── Create PlannedTask


Example:

Planner drags:

1010-1

onto:

Oven1 timeline


System creates:

PlannedTask
│
├── PlannedMachine = Oven1
├── StartTime = dropped position
├── EndTime = start + duration
└── ScenarioID = current scenario



====================================================
7. MACHINE AVAILABILITY MODEL
====================================================


Machine
│
├── EarliestAvailableTime
├── Timeline
└── Calendar


Example:

Oven1
│
├── EarliestAvailableTime = 08:00
└── Timeline = []


After scheduling:

1010-1
Duration = 14h


Oven1
│
├── EarliestAvailableTime = 22:00
└── Timeline
     └── 1010-1



====================================================
8. BUSINESS RULE ENGINE
====================================================


RuleEngine
│
├── Precedence Rules
├── OverSoak Rules
├── Gap Rules
├── Capacity Rules
├── Calendar Rules
└── Parallel Batch Rules



====================================================
9. CONFIGURABLE RULES
====================================================


RuleConfig
│
├── MaxOvenToPressGapMinutes
├── MaxPressToReheatGapMinutes
├── MaxOverSoakMinutes
├── AllowParallelOvens
├── AllowMachineOverlap
└── TemperatureTolerance


Example:

MaxOvenToPressGapMinutes = 10
MaxPressToReheatGapMinutes = 5
MaxOverSoakMinutes = 120


These should be:
- scenario configurable
- database configurable
- UI editable



====================================================
10. VIOLATION OBJECT
====================================================


Violation
│
├── ViolationID
├── PlannedTaskID
├── RuleType
├── Severity
├── Message
└── IsBlocking


Example:

Violation
│
├── RuleType = "OVER_SOAK"
├── Severity = "HIGH"
└── Message =
    "Oven soak exceeded by 47 minutes"



====================================================
11. GANTT VISUALIZATION RULES
====================================================


NORMAL TASK
----------------------------------------------------

Blue


MANUALLY MOVED TASK
----------------------------------------------------

Orange border


RULE VIOLATION
----------------------------------------------------

Red


HOVER TOOLTIP
----------------------------------------------------

Should show:

- WorkOrder
- Operation
- Sequence
- Machine
- Start
- End
- Duration
- Violations


Example Tooltip:

WO: 1010
Operation: 1010-3
Sequence: 3
Machine: Press1

Violation:
Over-soak exceeded by 47 minutes



====================================================
12. INTERACTIVE GANTT FEATURES
====================================================


InteractiveGantt
│
├── Drag & Drop
├── Resize Task
├── Context Menu
├── Dependency Arrows
├── Hover Tooltips
├── Parallel Oven Lanes
├── Violation Coloring
└── Manual Replanning
ZoomIn ZoomOut


====================================================
13. OVEN PARALLEL PROCESSING MODEL
====================================================


Oven1
│
├── Batch 1
│    ├── WO1010
│    ├── WO1011
│    └── WO1012
│
├── Batch 2
│    ├── WO1015
│    └── WO1016
│
└── ...


Visualization:
- same width
- stacked horizantally
- shorter height
- shared time span



====================================================
14. SCENARIO COMPARISON
====================================================


Scenario Comparison
│
├── KPI Comparison
├── Sequence Comparison
├── Machine Utilization
├── Late Orders
├── Setup Cost
├── Energy Usage
└── Manual Changes


Example:

Scenario A
- Cost = 2940
- Oven Util = 88%

Scenario B
- Cost = 3100
- Oven Util = 92%

Scenario C
- Manual adjustments
- Cost = 3500



====================================================
15. FUTURE DATABASE STRUCTURE
====================================================


TABLE: Scenario
----------------------------------------------------

ScenarioID
ScenarioName
BaseScenarioID
CreatedBy
CreatedDate
CalendarID



TABLE: PlannedTask
----------------------------------------------------

PlannedTaskID
ScenarioID
WorkOrderID
OperationID
MachineID
StartTime
EndTime
Duration
IsManual



TABLE: Violation
----------------------------------------------------

ViolationID
PlannedTaskID
RuleType
Severity
Message



TABLE: RuleConfiguration
----------------------------------------------------

RuleName
RuleValue
ScenarioID



====================================================
16. FINAL TARGET ARCHITECTURE
====================================================


APS Platform
│
├── Master Data
│    ├── Machines
│    ├── WorkOrders
│    └── Operations
│
├── Scenario Engine
│    ├── Scenario A
│    ├── Scenario B
│    └── Scenario C
│
├── Optimization Engine
│    ├── GA Scheduler
│    ├── Constraint Engine
│    └── Repair Engine
│
├── Manual Planning Engine
│    ├── Drag & Drop
│    ├── Rule Validation
│    └── Conflict Detection
│
├── Interactive Gantt
│
└── KPI Analytics



====================================================
17. IMPORTANT ARCHITECTURAL SHIFT
====================================================

NEW MODEL
----------------------------------------------------

GA creates PlannedTasks inside a Scenario.


This is VERY important because:

- manual planning becomes possible
- versioning becomes possible
- undo/redo becomes possible
- scenario comparison becomes possible
- collaborative planning becomes possible
- planner overrides become possible

