# ERAS (Enhanced Recovery After Surgery) - Future Design

> **Status**: Research complete, implementation deferred
> **Priority**: Phase 2 (after discharge instructions)
> **Last Updated**: 2025-06-11

## Overview

ERAS is a multimodal perioperative care pathway designed to reduce recovery time by 30%+ and complications. This document captures the research and design decisions for future implementation.

## ERAS Structure

### Four Phases

| Phase | Timing | Key Elements |
|-------|--------|--------------|
| **Preadmission** | T-4 weeks to T-1 day | Patient education, prehabilitation, nutrition optimization, smoking/alcohol cessation |
| **Preoperative** | Day of surgery, pre-incision | Carbohydrate loading (2-3h before), no prolonged fasting, thromboprophylaxis |
| **Intraoperative** | During surgery | Regional anesthesia, multimodal analgesia, goal-directed fluids, normothermia |
| **Postoperative** | Hospital → Discharge → Follow-up | Early mobilization (POD 0-1), early nutrition, catheter/drain removal, discharge criteria |

### Key Concepts

1. **Timeline-based milestones**: Actions tied to surgery date
   - `T-14d` = 14 days before surgery
   - `T-6h` = 6 hours before surgery
   - `POD0` = Post-operative day 0 (day of surgery)
   - `POD1`, `POD2`, etc.
   - `POD7-30` = Recovery period

2. **Evidence grading**: Each recommendation has strength
   - Strong (high-quality evidence)
   - Moderate (moderate-quality evidence)
   - Weak (low-quality evidence)

3. **Multidisciplinary ownership**: Elements assigned to roles
   - Patient
   - Nurse
   - Surgeon
   - Anesthetist
   - Dietician
   - Physiotherapist

4. **Patient visibility**: Some elements are clinician workflow only
   - "Order chest X-ray POD 1" (clinician)
   - "Walk for 10 minutes every 2 hours" (patient)

5. **Compliance tracking**: Track whether each element was completed
   - Required for RECOvER reporting
   - Links compliance rates to outcomes

6. **Milestones**: Discharge criteria and recovery targets
   - "Tolerating oral diet"
   - "Ambulating 6+ hours/day"
   - "Pain controlled with oral meds"

## Proposed Data Model Extensions

When implementing ERAS, extend the discharge instructions model:

### Additional Fields on CareProtocolTemplate

```python
# Protocol type
protocol_type: Mapped[str]  # "discharge_only" | "eras_full"

# ERAS-specific
eras_version: Mapped[str | None]  # e.g., "ERAS Society 2024"
surgery_specialty: Mapped[str | None]  # vascular, cardiac, colorectal, etc.
```

### New Table: ProtocolPhase

```python
class ProtocolPhase(Base):
    """Phase within an ERAS protocol"""
    __tablename__ = "sl_protocol_phase"

    id: Mapped[UUID]
    template_id: Mapped[UUID]  # FK to CareProtocolTemplate

    code: Mapped[str]  # preadmission, preoperative, intraoperative, postoperative
    name: Mapped[str]
    description: Mapped[str]

    # Timing relative to surgery
    timing_start: Mapped[str]  # e.g., "T-28d", "POD0"
    timing_end: Mapped[str]    # e.g., "T-1d", "POD3"

    sort_order: Mapped[int]
```

### New Table: ProtocolMilestone

```python
class ProtocolMilestone(Base):
    """Discharge criteria or recovery target"""
    __tablename__ = "sl_protocol_milestone"

    id: Mapped[UUID]
    template_id: Mapped[UUID]
    phase_id: Mapped[UUID | None]  # Optional phase association

    title: Mapped[str]
    description: Mapped[str]

    # Criteria can be a checklist
    criteria: Mapped[list[str]]  # ["Tolerating oral diet", "Pain controlled"]

    is_discharge_criterion: Mapped[bool]
    sort_order: Mapped[int]
```

### New Table: PatientProtocolCompliance

```python
class PatientProtocolCompliance(Base):
    """Track completion of protocol elements for a patient"""
    __tablename__ = "sl_patient_protocol_compliance"

    id: Mapped[UUID]
    patient_id: Mapped[UUID]
    patient_plan_id: Mapped[UUID]  # FK to PatientInstructionPlan

    # What was tracked
    element_id: Mapped[UUID]  # FK to ProtocolElement
    phase_code: Mapped[str]

    # Compliance status
    status: Mapped[str]  # pending, completed, skipped, not_applicable
    completed_at: Mapped[datetime | None]
    completed_by_id: Mapped[UUID | None]  # Practitioner or patient

    # Notes
    notes: Mapped[str | None]
    variance_reason: Mapped[str | None]  # If skipped, why?
```

### New Table: PatientMilestoneStatus

```python
class PatientMilestoneStatus(Base):
    """Track milestone achievement for a patient"""
    __tablename__ = "sl_patient_milestone_status"

    id: Mapped[UUID]
    patient_id: Mapped[UUID]
    milestone_id: Mapped[UUID]

    status: Mapped[str]  # pending, achieved, not_achieved
    achieved_at: Mapped[datetime | None]
    assessed_by_id: Mapped[UUID | None]

    # For checklist milestones, track individual criteria
    criteria_status: Mapped[dict | None]  # {"criterion_1": true, "criterion_2": false}
```

### Extended ProtocolElement Fields

```python
# Add to existing ProtocolElement (called ActivityTemplate in Phase 1)
evidence_level: Mapped[str | None]  # strong, moderate, weak
evidence_source: Mapped[str | None]  # "ERAS Society 2024 Guidelines"
default_responsible_role: Mapped[str | None]
patient_visible: Mapped[bool]  # Default True
compliance_trackable: Mapped[bool]  # Default True
phase_applicability: Mapped[list[str] | None]  # Which phases this applies to
```

## Content Structure Extension

When ERAS is implemented, the protocol content structure expands:

```json
{
  "phases": [
    {
      "id": "preadmission",
      "code": "preadmission",
      "name": "Preadmission",
      "timing_range": {"from": "T-28d", "to": "T-1d"},
      "description": "Preparation in the weeks before surgery",
      "elements": [
        {
          "id": "element-instance-id",
          "element_id": "uuid-of-protocol-element",
          "timing": "T-14d",
          "responsible_role": "nurse",
          "patient_visible": true,
          "compliance_required": true,
          "evidence_level": "strong",
          "overrides": {}
        }
      ],
      "milestones": [
        {
          "id": "prehab-complete",
          "title": "Prehabilitation program completed",
          "criteria": ["Completed 2-week exercise program", "Nutrition assessment done"],
          "is_discharge_criterion": false
        }
      ]
    },
    {
      "id": "postoperative-inpatient",
      "code": "postoperative",
      "name": "Postoperative (Inpatient)",
      "timing_range": {"from": "POD0", "to": "POD3"},
      "elements": [
        {
          "id": "early-mobilization",
          "element_id": "uuid",
          "timing": "POD0",
          "responsible_role": "nurse",
          "patient_visible": true,
          "compliance_required": true
        },
        {
          "id": "chest-xray-order",
          "element_id": "uuid",
          "timing": "POD1",
          "responsible_role": "surgeon",
          "patient_visible": false,
          "compliance_required": true
        }
      ],
      "milestones": [
        {
          "id": "discharge-ready",
          "title": "Ready for discharge",
          "criteria": [
            "Tolerating oral diet",
            "Pain controlled with oral medications",
            "Ambulating independently",
            "No signs of infection",
            "Understands discharge instructions"
          ],
          "is_discharge_criterion": true
        }
      ]
    }
  ]
}
```

## UI Components Needed for ERAS

### 1. Phase Timeline Builder
- Visual timeline showing all phases
- Drag elements between phases
- Set timing relative to surgery date

### 2. Compliance Dashboard
- Per-patient view of element completion
- Aggregate compliance rates across patients
- Variance tracking and reporting

### 3. Milestone Tracker
- Checklist UI for discharge criteria
- Progress indicators per milestone
- Discharge readiness summary

### 4. ERAS Reporting
- RECOvER-compatible compliance tables
- Element-by-element completion rates
- Outcome correlation (LOS, complications)

## FHIR Mapping

ERAS protocols map to FHIR resources:

| Our Model | FHIR Resource |
|-----------|---------------|
| CareProtocolTemplate | PlanDefinition |
| ProtocolElement | ActivityDefinition |
| ProtocolPhase | PlanDefinition.action (top-level grouping) |
| PatientInstructionPlan | CarePlan |
| PatientProtocolCompliance | CarePlan.activity.detail.status |
| PatientMilestoneStatus | Goal |

## References

- [ERAS Society](https://erassociety.org/)
- [RECOvER Checklist - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6313353/)
- [ERAS Protocol Advances - PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10654132/)
- [TeachMeSurgery - ERAS Overview](https://teachmesurgery.com/perioperative/preoperative/enhanced-recovery-surgery/)
- [SVS/ERAS Vascular Guidelines](https://vascular.org/vascular-specialists/practice-and-quality/clinical-guidelines/clinical-guidelines-and-reporting-7)

## Migration Path

When implementing ERAS:

1. Add `protocol_type` to CareProtocolTemplate (default: "discharge_only")
2. Create ProtocolPhase table
3. Create ProtocolMilestone table
4. Create PatientProtocolCompliance table
5. Create PatientMilestoneStatus table
6. Extend ProtocolElement with ERAS fields
7. Build phase timeline UI
8. Build compliance tracking UI
9. Build reporting dashboards

Existing discharge instruction templates remain valid - they're just single-phase ERAS protocols with `protocol_type = "discharge_only"`.
