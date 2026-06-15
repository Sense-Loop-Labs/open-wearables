# Instruction Templates - Design Document

> **Status**: Ready for implementation
> **Priority**: Phase 1
> **Last Updated**: 2025-06-11

## Overview

This document describes the design for flexible instruction templates that support:
- Post-surgical discharge instructions
- Chronic condition management (hypertension, diabetes, etc.)
- General health guidance and care plans

The design is extensible to support full ERAS protocols in the future (see ERAS_DESIGN.md).

## Use Cases

### 1. Post-Surgical Discharge Instructions
- Patient receives surgery-specific care instructions
- Wound care, medication schedules, activity restrictions
- Warning signs to watch for
- Follow-up appointment reminders

### 2. Chronic Condition Management (e.g., Hypertension)
- Daily/weekly monitoring schedules (BP readings)
- Medication adherence guidance
- Lifestyle modifications (diet, exercise)
- Symptom questionnaires
- Warning sign education

### 3. General Wellness Programs
- Cardiac rehabilitation
- Weight management
- Preventive care protocols

## Data Model

### Core Tables

#### 1. sl_activity_template
Reusable instruction building blocks (e.g., "Daily Wound Care", "BP Monitoring").

```python
class ActivityTemplate(Base):
    __tablename__ = "sl_activity_template"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_organization.id"),
        nullable=True,  # None = shared/global template
        index=True
    )

    # Metadata
    name: Mapped[str] = mapped_column(String(100), unique=True)  # Machine-readable slug
    title: Mapped[str] = mapped_column(String(255))  # Display name
    description: Mapped[str] = mapped_column(Text)  # Rich HTML content
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, active, retired
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")

    # Classification
    category_code: Mapped[str] = mapped_column(String(50))  # wound-care, medications, activity, etc.
    kind: Mapped[str] = mapped_column(String(50), default="task")  # task, service_request, medication_request

    # Flexible content (JSONB)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)  # Structured content
    timing: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # FHIR-compatible timing

    # FHIR interop
    code_system: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g., SNOMED CT
    code_value: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Audit
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("sl_practitioner.id"))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="activity_templates")
    created_by = relationship("Practitioner")
```

#### 2. sl_instruction_template
Complete instruction templates combining multiple activities into sections.

```python
class InstructionTemplate(Base):
    __tablename__ = "sl_instruction_template"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_organization.id"),
        nullable=True,  # None = shared/global template
        index=True
    )

    # Metadata
    name: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")

    # Content structure (JSONB)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Audit
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("sl_practitioner.id"))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="instruction_templates")
    created_by = relationship("Practitioner")
    health_focuses = relationship("InstructionTemplateHealthFocus", back_populates="template")
```

#### 3. sl_instruction_template_health_focus
Join table linking templates to health focus codes.

```python
class InstructionTemplateHealthFocus(Base):
    __tablename__ = "sl_instruction_template_health_focus"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_instruction_template.id", ondelete="CASCADE"),
        index=True
    )
    health_focus_code: Mapped[str] = mapped_column(String(100))  # References ValueSet item

    # Relationships
    template = relationship("InstructionTemplate", back_populates="health_focuses")

    __table_args__ = (
        UniqueConstraint("template_id", "health_focus_code"),
    )
```

#### 4. sl_patient_instruction_plan
Patient-specific instance linking a patient to a template.

```python
class PatientInstructionPlan(Base):
    __tablename__ = "sl_patient_instruction_plan"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_patient.id", ondelete="CASCADE"),
        index=True
    )
    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_instruction_template.id"),
        index=True
    )

    # Status
    status: Mapped[str] = mapped_column(String(20), default="active")  # draft, active, completed, cancelled
    effective_start: Mapped[datetime] = mapped_column(default=func.now())
    effective_end: Mapped[datetime | None] = mapped_column(nullable=True)

    # Customizations (JSONB) - overrides template content
    customizations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Resolved content (cached, denormalized for fast reads)
    resolved_content: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Audit
    assigned_by_id: Mapped[UUID] = mapped_column(ForeignKey("sl_practitioner.id"))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    patient = relationship("Patient", back_populates="instruction_plans")
    template = relationship("InstructionTemplate")
    assigned_by = relationship("Practitioner")
```

### Content Structures

#### Activity Template Content

```json
{
  "instructions": "Keep the incision site clean and dry for 48 hours.",
  "warnings": ["Redness spreading from incision", "Fever above 101°F"],
  "tips": ["Use a clean towel each time", "Pat dry, don't rub"],
  "resources": [
    {
      "type": "video",
      "title": "Wound Care Demonstration",
      "url": "https://..."
    }
  ]
}
```

#### Instruction Template Content

```json
{
  "sections": [
    {
      "id": "wound-care",
      "title": "Wound Care",
      "description": "How to care for your surgical incision",
      "priority": "routine",
      "items": [
        {
          "id": "daily-wound-check",
          "type": "activity_ref",
          "activity_template_id": "uuid-of-activity",
          "timing": {
            "frequency": 1,
            "period": 1,
            "periodUnit": "d"
          }
        },
        {
          "id": "keep-dry",
          "type": "inline",
          "title": "Keep incision dry for 48 hours",
          "description": "Do not submerge in water. Showers OK after 48 hours."
        }
      ]
    },
    {
      "id": "warning-signs",
      "title": "When to Call Your Doctor",
      "priority": "urgent",
      "items": [
        {
          "id": "fever",
          "type": "inline",
          "title": "Fever above 101°F (38.3°C)"
        },
        {
          "id": "redness",
          "type": "inline",
          "title": "Redness spreading from incision site"
        },
        {
          "id": "drainage",
          "type": "inline",
          "title": "Increased drainage or foul-smelling discharge"
        }
      ]
    },
    {
      "id": "medications",
      "title": "Medications",
      "items": [
        {
          "id": "pain-management",
          "type": "activity_ref",
          "activity_template_id": "uuid-of-pain-med-activity",
          "timing": {
            "frequency": 1,
            "period": 6,
            "periodUnit": "h",
            "boundsRange": {
              "low": {"value": 0, "unit": "d"},
              "high": {"value": 7, "unit": "d"}
            }
          }
        }
      ]
    },
    {
      "id": "follow-up",
      "title": "Follow-Up Care",
      "items": [
        {
          "id": "appointment",
          "type": "inline",
          "title": "Schedule follow-up appointment",
          "description": "Call to schedule within 2 weeks of surgery"
        }
      ]
    }
  ]
}
```

#### Timing Structure (FHIR-compatible)

```json
{
  "frequency": 2,
  "period": 1,
  "periodUnit": "d",
  "dayOfWeek": ["mon", "wed", "fri"],
  "timeOfDay": ["08:00", "20:00"],
  "boundsRange": {
    "low": {"value": 0, "unit": "d"},
    "high": {"value": 14, "unit": "d"}
  }
}
```

Common patterns:
- Daily: `{"frequency": 1, "period": 1, "periodUnit": "d"}`
- Twice daily: `{"frequency": 2, "period": 1, "periodUnit": "d"}`
- Every 8 hours: `{"frequency": 3, "period": 1, "periodUnit": "d"}`
- Weekly on M/W/F: `{"period": 1, "periodUnit": "wk", "dayOfWeek": ["mon", "wed", "fri"]}`
- For 7 days: Add `boundsRange` with `high: {value: 7, unit: "d"}`

### Activity Categories

Seed a ValueSet with activity categories:

| Code | Display | Color |
|------|---------|-------|
| wound-care | Wound Care | red |
| medications | Medications | blue |
| activity | Activity & Exercise | green |
| diet | Diet & Nutrition | orange |
| follow-up | Follow-up Care | violet |
| warning-signs | Warning Signs | pink |
| monitoring | Self-Monitoring | cyan |
| education | Patient Education | indigo |
| other | Other | gray |

### Health Focus Codes

Seed a ValueSet with health focus options:

| Code | Display | Category |
|------|---------|----------|
| post-angioplasty | Post-Angioplasty Recovery | surgical |
| post-bypass | Post-Bypass Recovery | surgical |
| post-carotid | Post-Carotid Surgery Recovery | surgical |
| post-aneurysm | Post-Aneurysm Repair Recovery | surgical |
| hypertension | Hypertension Management | chronic |
| diabetes-type2 | Type 2 Diabetes Management | chronic |
| heart-failure | Heart Failure Management | chronic |
| afib | Atrial Fibrillation Management | chronic |
| cardiac-rehab | Cardiac Rehabilitation | preventive |
| weight-management | Weight Management | preventive |

## API Endpoints

### Activity Templates

```
GET    /api/v1/sl/activity-templates          # List (with org/shared filtering)
POST   /api/v1/sl/activity-templates          # Create
GET    /api/v1/sl/activity-templates/{id}     # Get
PUT    /api/v1/sl/activity-templates/{id}     # Update
DELETE /api/v1/sl/activity-templates/{id}     # Delete (soft - set status=retired)
```

### Instruction Templates

```
GET    /api/v1/sl/instruction-templates       # List (with org/shared filtering)
POST   /api/v1/sl/instruction-templates       # Create
GET    /api/v1/sl/instruction-templates/{id}  # Get
PUT    /api/v1/sl/instruction-templates/{id}  # Update
DELETE /api/v1/sl/instruction-templates/{id}  # Delete (soft)
GET    /api/v1/sl/instruction-templates/{id}/preview  # Resolved preview
POST   /api/v1/sl/instruction-templates/{id}/duplicate  # Copy template
```

### Patient Instruction Plans

```
GET    /api/v1/sl/patients/{id}/instruction-plans      # List patient's plans
POST   /api/v1/sl/patients/{id}/instruction-plans      # Assign template to patient
GET    /api/v1/sl/patients/{id}/instruction-plans/{id} # Get specific plan
PUT    /api/v1/sl/patients/{id}/instruction-plans/{id} # Update (customizations)
DELETE /api/v1/sl/patients/{id}/instruction-plans/{id} # Cancel plan
```

### Mobile API

```
POST   /api/v1/sl/mobile/instructions         # Get patient's active instructions
```

## Frontend Components

### 1. ActivityTemplateForm
Form for creating/editing activity templates.

Fields:
- Title (auto-generates name slug)
- Category (dropdown from ValueSet)
- Kind (task, service_request, medication_request)
- Description (rich text editor)
- Timing (timing editor component)
- Status (draft, active, retired)
- Version

### 2. InstructionBuilder
Visual builder for instruction templates.

Features:
- Section management (add, edit, delete, reorder)
- Item management within sections (add from library or inline)
- Timing configuration per item
- Priority badges (routine, urgent)
- Preview mode

### 3. ActivityLibrary
Modal for browsing and selecting activity templates.

Features:
- Filter by category
- Filter by organization (shared vs. org-specific)
- Search by title
- Preview activity details
- Add to instruction template

### 4. TimingEditor
Component for configuring frequency/timing.

Features:
- Presets (daily, twice daily, weekly, etc.)
- Custom configuration
- Duration/bounds setting
- Day-of-week selection
- Time-of-day specification

### 5. InstructionTemplateList
Admin page listing all templates.

Features:
- Filter by status, health focus, organization
- Sort by title, updated date
- Quick actions (edit, duplicate, preview, retire)
- Shared vs. org-specific badge

### 6. PatientInstructionAssignment
Component on patient edit page for assigning instructions.

Features:
- Template selection (filtered by patient's health focus)
- Preview before assignment
- Customization options
- View/edit assigned plans

## FHIR Transformation

### ActivityTemplate → FHIR ActivityDefinition

```python
def activity_to_fhir(activity: ActivityTemplate) -> dict:
    return {
        "resourceType": "ActivityDefinition",
        "id": str(activity.id),
        "url": f"https://senseloop.health/ActivityDefinition/{activity.name}",
        "name": activity.name,
        "title": activity.title,
        "status": activity.status,
        "description": activity.description,
        "kind": map_kind_to_fhir(activity.kind),
        "timingTiming": activity.timing,
        "code": {
            "coding": [{
                "system": activity.code_system,
                "code": activity.code_value
            }]
        } if activity.code_value else None,
        "extension": [{
            "url": "https://senseloop.health/activity-category",
            "valueCode": activity.category_code
        }]
    }
```

### InstructionTemplate → FHIR PlanDefinition

```python
def template_to_fhir(template: InstructionTemplate) -> dict:
    return {
        "resourceType": "PlanDefinition",
        "id": str(template.id),
        "url": f"https://senseloop.health/PlanDefinition/{template.name}",
        "name": template.name,
        "title": template.title,
        "status": template.status,
        "version": template.version,
        "description": template.description,
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/plan-definition-type",
                "code": "clinical-protocol"
            }]
        },
        "useContext": [
            {
                "code": {"code": "focus"},
                "valueCodeableConcept": {
                    "coding": [{"code": hf.health_focus_code}]
                }
            }
            for hf in template.health_focuses
        ],
        "action": [
            section_to_fhir_action(section)
            for section in template.content.get("sections", [])
        ]
    }
```

### PatientInstructionPlan → FHIR CarePlan

```python
def plan_to_fhir(plan: PatientInstructionPlan, patient: Patient) -> dict:
    return {
        "resourceType": "CarePlan",
        "id": str(plan.id),
        "status": map_status_to_fhir(plan.status),
        "intent": "plan",
        "subject": {"reference": f"Patient/{patient.id}"},
        "instantiatesCanonical": [
            f"PlanDefinition/{plan.template_id}"
        ],
        "period": {
            "start": plan.effective_start.isoformat(),
            "end": plan.effective_end.isoformat() if plan.effective_end else None
        }
    }
```

## Migration Path

1. Create migration for new tables
2. Seed activity categories ValueSet
3. Seed health focus ValueSet
4. Create API routes and schemas
5. Build frontend components
6. Update mobile API to use new structure
7. Migrate existing CarePlan data to new model (if needed)

## Testing Strategy

### Unit Tests
- Model validation
- FHIR transformation accuracy
- Content structure validation

### Integration Tests
- API endpoint CRUD operations
- Template resolution with activity references
- Patient plan assignment flow

### E2E Tests
- Create activity template flow
- Create instruction template with activities
- Assign template to patient
- Mobile app receives instructions
