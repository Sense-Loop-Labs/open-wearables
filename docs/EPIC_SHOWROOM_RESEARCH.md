# Epic Showroom Integration Research

*Research conducted August 2026*

---

## Executive Summary

**Epic Showroom** (formerly App Orchard) is Epic's customer-facing marketplace where hospitals and clinics discover, evaluate, and request third-party software that integrates with Epic EHR systems.

**Why it matters:** Epic controls **36%+ of the US hospital EHR market** and is used by 28 of the top 30 US hospitals. Listing on Showroom provides visibility and credibility with enterprise healthcare customers.

**Key finding:** Getting listed requires technical integration (FHIR/SMART on FHIR), security certifications (SOC 2 Type II), and at least one live Epic customer. The process takes 6-12+ months and costs $50K-$200K+ depending on integration depth.

---

## What is Epic Showroom?

Epic Showroom is a marketplace where:
- Hospitals discover vetted third-party solutions
- Vendors showcase products that integrate with Epic
- Trust is established through Epic's review process

**Important distinction:** Showroom is a *discovery channel*, not a hosting or compliance platform. Vendors must independently obtain security certifications and maintain their own infrastructure.

### Evolution from App Orchard

| Era | Program | Notes |
|-----|---------|-------|
| Mid-2010s | App Orchard | Original marketplace, up to 30% revenue share |
| 2022 | Transition | App Orchard discontinued |
| Current | Showroom + Vendor Services | Restructured program with new fee model |

---

## Requirements Overview

### 1. Technical Requirements

| Requirement | Description | Mandatory? |
|-------------|-------------|------------|
| **FHIR R4 APIs** | HL7 FHIR R4 standard for data exchange | Yes |
| **SMART on FHIR** | Framework for launching apps within Epic workflow | Yes (for embedded apps) |
| **OAuth 2.0** | Authorization with short-lived tokens (5-60 min) | Yes |
| **PKCE** | Proof Key for Code Exchange for browser/mobile apps | Yes |
| **TLS 1.2+** | HTTPS encryption for all communications | Yes |
| **ONC g10 Conformance** | Federal certification for EHR app interoperability | Yes |
| **HL7 v2** | Legacy messaging for real-time events (optional) | Situational |

### 2. Security & Compliance Requirements

| Requirement | Description | Typical Cost |
|-------------|-------------|--------------|
| **SOC 2 Type II** | Annual audit of security controls | $50K-$150K first year |
| **HIPAA Compliance** | BAA, compliant hosting, policies | Varies |
| **Penetration Test** | Third-party security assessment | $10K-$30K |
| **Data Flow Diagrams** | Documentation of PHI movement | Internal effort |
| **Incident Response Plan** | Business continuity documentation | Internal effort |
| **Security Training** | Employee training documentation | Internal effort |

### 3. Business Requirements

| Requirement | Description |
|-------------|-------------|
| **Live Customer** | At least one Epic customer in production |
| **Vendor Services Membership** | Annual subscription for tools/support |
| **Connection Hub Registration** | Formal listing registration |

---

## Epic Program Tiers

### Open.epic (Free)

- Basic FHIR sandbox access
- Limited documentation
- No technical support
- Good for initial exploration

**URL:** https://open.epic.com

### Vendor Services ($1,900/year)

- Full sandbox environments
- Testing tools and client harnesses
- Expert design consultation
- Deployment assistance
- Expanded API catalog
- Technical support access

**Includes 3-month trial period with refund option.**

### Connection Hub ($500/year)

- Maintains marketplace listing
- Requires at least one live customer connection
- Customer-facing visibility

### Showroom Listing

- Achieved after Connection Hub + live customer
- Marketplace visibility to Epic customers
- Credibility signal for sales

---

## Cost Breakdown

### Program Fees

| Item | Cost | Frequency |
|------|------|-----------|
| Vendor Services membership | $1,900 | Annual |
| Connection Hub listing | $500 | Annual |
| Marketplace fees & certification | $5,000-$25,000 | One-time |

### Development Costs

| Integration Type | Cost Range | Timeline |
|------------------|------------|----------|
| FHIR read-only | $40,000-$80,000 | 2-4 months |
| FHIR read/write | $80,000-$180,000 | 4-8 months |
| SMART on FHIR embedded | $60,000-$150,000 | 3-7 months |
| HL7 v2 single interface | $30,000-$60,000 | 2-3 months |
| Full bidirectional | $150,000-$350,000+ | 6-14 months |

### Ongoing Costs

| Item | Cost | Frequency |
|------|------|-----------|
| Per-site activation | $10,000-$40,000 | Per hospital |
| Annual maintenance | $15,000-$50,000 | Per integration |
| Integration engine hosting | $1,000-$5,000 | Monthly |

---

## Timeline

### Typical Milestones

```
Month 1-2:    Register for Vendor Services, access sandbox
Month 2-4:    Develop FHIR/SMART integration
Month 3-6:    SOC 2 Type II audit (parallel track)
Month 4-6:    Epic marketplace review (2-4 months)
Month 6-9:    First customer site activation (1-3 months)
Month 9+:     Showroom listing active
```

**Critical insight:** "The approval process at Epic and at individual customer sites often takes longer than the actual development."

### Per-Site Activation

Each Epic customer site must independently:
1. Approve your integration
2. Configure connection settings
3. Complete site-specific testing
4. Conduct go-live approval

This takes **1-3 months per site** even after marketplace approval.

---

## Integration Pathways

### Option A: SMART on FHIR Embedded App

**Description:** App launches from within Epic Hyperspace/Hyperdrive. Clinician clicks app, patient context passes automatically.

**Use case:** Clinician dashboard showing wearable data alongside EHR data.

**Components required:**
1. SMART on FHIR launch context handling
2. OAuth 2.0 authorization with appropriate scopes
3. FHIR R4 read of patient/encounter context
4. FHIR R4 write-back (optional)
5. App Orchard certification

**Effort:** 3-7 months, $60K-$150K

### Option B: Data Pipeline Integration

**Description:** Push wearable data to Epic as FHIR Observations. No UI embedding.

**Use case:** Wearable health data appears in Epic flowsheets/charts.

**Components required:**
1. FHIR R4 API for data submission
2. Observation resource mapping
3. Authentication/authorization

**Effort:** 2-4 months, $40K-$80K

### Option C: CDS Hooks Integration

**Description:** Clinical decision support alerts within Epic workflow.

**Use case:** "Patient HRV dropped 30% - review wearable data"

**Components required:**
1. CDS Hooks service implementation
2. Alert card generation
3. Deep linking to detailed view

**Effort:** 4-6 months (additional to above)

### Option D: HL7 v2 Messaging

**Description:** Real-time event notifications via legacy protocol.

**Use case:** ADT messages trigger data sync, results flow back.

**Components required:**
1. HL7 v2 interface engine
2. Message parsing/generation
3. VPN/secure transport

**Effort:** 2-3 months per interface, $30K-$60K

---

## Challenges for Startups

### 1. Chicken-and-Egg Problem

You need a live customer to get listed, but customers often want listed vendors.

**Solution:** Find a champion hospital willing to pilot with an unlisted vendor.

### 2. Enterprise Sales Cycle

Epic customers are large organizations with complex procurement:
- IT Security review
- Legal/compliance review
- Procurement/finance approval
- Clinical champion advocacy

Your user is rarely the buyer or decision-maker.

### 3. Per-Site Variability

Each Epic installation is customized:
- UI/workflow modifications
- Business logic rules
- Reference data configurations
- Custom data elements

Success at one organization doesn't guarantee success at another.

### 4. Hidden Costs

Beyond published fees:
- Usage-based API charges
- Technical support at premium rates
- Extended sales cycles requiring pre-sales engineering

### 5. BAA Requirements

Business Associate Agreements must be signed by entities with legal authority. This prevents bottom-up adoption and forces traditional enterprise sales.

### 6. API Access Opacity

Developers must submit "Interoperability Request" forms for specific APIs. The process is described as a "black box" with limited visibility into decisions.

**Recommendation:** Secure support from 2-3 potential customers before submitting API requests.

---

## Gap Analysis: Open Wearables / Recovery Companion

### Current Capabilities

| Capability | Status | Notes |
|------------|--------|-------|
| HIPAA-compliant hosting | ✅ Have | AWS with encryption, audit logging |
| OAuth 2.0 authentication | ✅ Have | Implemented for current auth |
| RESTful APIs | ✅ Have | FastAPI backend |
| Patient health data | ✅ Have | Wearable data pipeline |
| Audit logging | ✅ Have | sense_loop/models/audit_log.py |
| Push notifications | ✅ Have | FCM integration |

### Gaps to Address

| Requirement | Current State | Effort to Address |
|-------------|---------------|-------------------|
| **FHIR R4 APIs** | Custom schemas | Medium-High: Build FHIR resource layer |
| **SMART on FHIR launch** | Standalone app | High: Implement EHR launch flow |
| **SOC 2 Type II** | Not certified | 6-12 months, $50K-$150K |
| **Penetration test** | No formal report | $10K-$30K |
| **Epic sandbox testing** | Not started | Medium: Integration work |
| **FHIR write-back** | PostgreSQL only | Medium: Map to FHIR resources |
| **Live Epic customer** | None | Sales/BD effort |

---

## Recommended Path Forward

### Phase 1: Foundation (Months 1-3)

1. **Start SOC 2 Type II process** - This is the longest lead time item
2. **Register for Vendor Services** ($1,900) - Get sandbox access
3. **Explore Epic sandbox** - Understand FHIR/SMART capabilities
4. **Identify pilot customer** - Find champion hospital

### Phase 2: Technical Integration (Months 2-6)

1. **Build FHIR R4 mapping layer** - Expose health data as FHIR Observations
2. **Implement SMART on FHIR launch** - Enable EHR-embedded launch
3. **Test against Epic sandbox** - Validate integration
4. **Complete penetration testing** - Third-party assessment

### Phase 3: Certification (Months 4-8)

1. **Submit for marketplace review** - 2-4 month process
2. **Complete SOC 2 audit** - Finalize certification
3. **Prepare customer deployment** - Documentation, training

### Phase 4: Go-Live (Months 6-12)

1. **Activate first customer site** - 1-3 months
2. **Register on Connection Hub** - $500/year
3. **Achieve Showroom listing** - Marketplace visibility

---

---

## Deep Dive: FHIR R4 for Wearable Data

### What is FHIR?

**FHIR (Fast Healthcare Interoperability Resources)** is the modern standard for healthcare data exchange. It uses:
- RESTful APIs (familiar to web developers)
- JSON or XML data formats
- Standardized resources (Patient, Observation, etc.)
- OAuth 2.0 for authentication

### The Observation Resource

The **Observation** resource is the primary way to represent wearable health data in FHIR. It captures measurements like heart rate, steps, sleep, and HRV.

**Required Fields:**
| Field | Description |
|-------|-------------|
| `status` | Observation status: `registered`, `preliminary`, `final`, `amended` |
| `code` | What was measured (LOINC code) |

**Common Optional Fields:**
| Field | Description |
|-------|-------------|
| `subject` | Reference to Patient resource |
| `effectiveDateTime` | When the measurement was taken |
| `value[x]` | The actual value (Quantity, string, integer, etc.) |
| `performer` | Who/what performed the measurement |
| `device` | Reference to the device that took the measurement |

### LOINC Codes for Wearable Data

LOINC (Logical Observation Identifiers Names and Codes) provides standardized codes for clinical observations. Here are the key codes for wearable health data:

| Metric | LOINC Code | Description | Units (UCUM) |
|--------|------------|-------------|--------------|
| **Heart Rate** | `8867-4` | Heart rate | `/min` (beats per minute) |
| **Resting Heart Rate** | `40443-4` | Heart rate - resting | `/min` |
| **HRV (SDNN)** | `80404-7` | R-R interval standard deviation | `ms` |
| **Steps (24h)** | `41950-7` | Number of steps in 24 hour | `{steps}` |
| **Steps (unspecified)** | `55423-8` | Number of steps - pedometer | `{steps}` |
| **Sleep Duration** | `93832-4` | Sleep duration | `h` (hours) |
| **Exercise Minutes** | `82290-8` | Moderate-vigorous activity minutes/week | `min/wk` |
| **Body Weight** | `29463-7` | Body weight | `kg` or `[lb_av]` |
| **Body Temperature** | `8310-5` | Body temperature | `Cel` or `[degF]` |
| **Blood Pressure (Systolic)** | `8480-6` | Systolic blood pressure | `mm[Hg]` |
| **Blood Pressure (Diastolic)** | `8462-4` | Diastolic blood pressure | `mm[Hg]` |
| **Oxygen Saturation** | `59408-5` | Oxygen saturation (SpO2) | `%` |

### Example: Heart Rate Observation (JSON)

```json
{
  "resourceType": "Observation",
  "id": "heart-rate-example",
  "status": "final",
  "category": [
    {
      "coding": [
        {
          "system": "http://terminology.hl7.org/CodeSystem/observation-category",
          "code": "vital-signs",
          "display": "Vital Signs"
        }
      ]
    }
  ],
  "code": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "8867-4",
        "display": "Heart rate"
      }
    ]
  },
  "subject": {
    "reference": "Patient/123"
  },
  "effectiveDateTime": "2026-08-27T14:30:00Z",
  "valueQuantity": {
    "value": 72,
    "unit": "beats/minute",
    "system": "http://unitsofmeasure.org",
    "code": "/min"
  },
  "device": {
    "display": "Apple Watch Series 9"
  }
}
```

### Example: Steps Observation (JSON)

```json
{
  "resourceType": "Observation",
  "id": "steps-example",
  "status": "final",
  "category": [
    {
      "coding": [
        {
          "system": "http://terminology.hl7.org/CodeSystem/observation-category",
          "code": "activity",
          "display": "Activity"
        }
      ]
    }
  ],
  "code": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "41950-7",
        "display": "Number of steps in 24 hour"
      }
    ]
  },
  "subject": {
    "reference": "Patient/123"
  },
  "effectivePeriod": {
    "start": "2026-08-27T00:00:00Z",
    "end": "2026-08-27T23:59:59Z"
  },
  "valueQuantity": {
    "value": 8547,
    "unit": "steps",
    "system": "http://unitsofmeasure.org",
    "code": "{steps}"
  }
}
```

### Example: Sleep Duration Observation (JSON)

```json
{
  "resourceType": "Observation",
  "id": "sleep-example",
  "status": "final",
  "category": [
    {
      "coding": [
        {
          "system": "http://terminology.hl7.org/CodeSystem/observation-category",
          "code": "activity",
          "display": "Activity"
        }
      ]
    }
  ],
  "code": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "93832-4",
        "display": "Sleep duration"
      }
    ]
  },
  "subject": {
    "reference": "Patient/123"
  },
  "effectivePeriod": {
    "start": "2026-08-26T22:30:00Z",
    "end": "2026-08-27T06:45:00Z"
  },
  "valueQuantity": {
    "value": 8.25,
    "unit": "hours",
    "system": "http://unitsofmeasure.org",
    "code": "h"
  }
}
```

### Mapping Open Wearables Data to FHIR

| Open Wearables Model | FHIR Resource | LOINC Code |
|---------------------|---------------|------------|
| `data_point_series` (heart_rate) | Observation | 8867-4 |
| `data_point_series` (resting_hr) | Observation | 40443-4 |
| `data_point_series` (hrv) | Observation | 80404-7 |
| `data_point_series` (steps) | Observation | 41950-7 |
| `event_record` (sleep) | Observation | 93832-4 |
| `event_record` (workout) | Observation | Custom or 73985-4 |
| `health_score` (sleep_score) | Observation | Custom |
| `health_score` (recovery_score) | Observation | Custom |

### Write Access Considerations

**Important:** Write access to Epic FHIR APIs is limited.

- **Read access**: Commonly available
- **Write access**: Restricted, requires per-site approval
- **Observation writes**: Supported for patient-generated data (like RPM readings)
- **DocumentReference writes**: Supported for clinical notes and documents

**Best Practice:** Confirm write support with each hospital before committing to a FHIR-only approach. Some Epic instances require HL7 v2 interfaces for certain data types.

---

## Deep Dive: SMART on FHIR Authentication

### What is SMART on FHIR?

**SMART on FHIR** (Substitutable Medical Applications, Reusable Technologies) is a healthcare-specific layer on top of OAuth 2.0. It standardizes:
- How apps authenticate with EHRs
- How apps receive patient/encounter context
- What permissions (scopes) apps can request
- How tokens are issued and refreshed

### Launch Types

#### EHR Launch (Embedded App)

The app launches from within the EHR (e.g., clinician clicks app icon in Epic).

```
1. Clinician working in Epic
2. Clicks "Recovery Companion" in app menu
3. Epic redirects to your app with:
   - launch parameter (opaque identifier)
   - iss parameter (FHIR server URL)
4. App uses these to request authorization
5. After auth, app receives patient/encounter context
```

**Use Case:** Clinician dashboard embedded in Epic showing patient's wearable data.

#### Standalone Launch (Independent App)

The app launches independently (e.g., patient opens mobile app).

```
1. Patient opens Recovery Companion app
2. App redirects to Epic patient portal for auth
3. Patient logs in and grants access
4. App receives authorization code
5. App exchanges code for tokens
6. App can now access patient's FHIR data
```

**Use Case:** Patient mobile app syncing wearable data to Epic.

### OAuth 2.0 Authorization Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Your App      │     │  Authorization  │     │   FHIR Server   │
│                 │     │     Server      │     │                 │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │  1. Discovery         │                       │
         │─────────────────────────────────────────────►│
         │  GET /.well-known/smart-configuration        │
         │◄─────────────────────────────────────────────│
         │                       │                       │
         │  2. Authorization Request                     │
         │──────────────────────►│                       │
         │  (redirect user)      │                       │
         │                       │                       │
         │  3. User Login & Consent                      │
         │                       │  (user authenticates) │
         │                       │                       │
         │  4. Authorization Code                        │
         │◄──────────────────────│                       │
         │  (redirect with code) │                       │
         │                       │                       │
         │  5. Token Exchange    │                       │
         │──────────────────────►│                       │
         │  POST /token          │                       │
         │◄──────────────────────│                       │
         │  (access_token,       │                       │
         │   refresh_token)      │                       │
         │                       │                       │
         │  6. Access FHIR Resources                     │
         │─────────────────────────────────────────────►│
         │  GET /Patient/123     │                       │
         │◄─────────────────────────────────────────────│
         │                       │                       │
```

### Step 1: Discovery

Fetch the SMART configuration from the FHIR server:

```
GET https://fhir.epic.com/.well-known/smart-configuration
```

Response:
```json
{
  "authorization_endpoint": "https://fhir.epic.com/oauth2/authorize",
  "token_endpoint": "https://fhir.epic.com/oauth2/token",
  "token_endpoint_auth_methods_supported": ["client_secret_basic", "private_key_jwt"],
  "scopes_supported": ["openid", "fhirUser", "launch", "patient/*.read", "user/*.read"],
  "capabilities": ["launch-ehr", "launch-standalone", "context-ehr-patient"]
}
```

### Step 2: Authorization Request

Redirect user to authorization endpoint:

```
https://fhir.epic.com/oauth2/authorize?
  response_type=code&
  client_id=your-client-id&
  redirect_uri=https://yourapp.com/callback&
  scope=launch/patient openid fhirUser patient/Observation.read&
  state=abc123xyz&
  aud=https://fhir.epic.com/api/FHIR/R4&
  code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&
  code_challenge_method=S256
```

### Step 3: Token Exchange

After user authorizes, exchange the code for tokens:

```
POST https://fhir.epic.com/oauth2/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=authorization-code-here&
redirect_uri=https://yourapp.com/callback&
client_id=your-client-id&
code_verifier=original-code-verifier
```

Response:
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "launch/patient openid fhirUser patient/Observation.read",
  "refresh_token": "refresh-token-here",
  "patient": "123",
  "fhirUser": "Practitioner/456"
}
```

**Note:** The response includes `patient` context - the FHIR Patient ID.

### SMART Scopes

Scope format: `<context>/<resource>.<permissions>`

| Scope | Description |
|-------|-------------|
| `openid` | Get user identity (OIDC) |
| `fhirUser` | Get FHIR resource representing user |
| `launch` | Receive EHR launch context |
| `launch/patient` | Receive patient context |
| `patient/Observation.read` | Read observations for current patient |
| `patient/Observation.write` | Write observations for current patient |
| `patient/*.read` | Read all resources for current patient |
| `user/Observation.read` | Read observations user has access to |
| `offline_access` | Get refresh token (valid 90+ days) |
| `online_access` | Get refresh token (valid while user logged in) |

**Permission Shortcuts:**
- `c` = create
- `r` = read
- `u` = update
- `d` = delete
- `s` = search

Example: `patient/Observation.crs` = create, read, search observations

### PKCE (Proof Key for Code Exchange)

**Required for all SMART apps**, especially mobile/browser apps.

```python
import secrets
import hashlib
import base64

# Generate code verifier (43-128 characters)
code_verifier = secrets.token_urlsafe(32)

# Generate code challenge (SHA256 hash, base64url encoded)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).decode().rstrip('=')
```

Include `code_challenge` in authorization request, `code_verifier` in token exchange.

### Token Security Best Practices

| Practice | Implementation |
|----------|----------------|
| **TLS 1.2+** | All API calls over HTTPS |
| **Short-lived tokens** | Access tokens expire in ≤1 hour |
| **Secure storage** | iOS Keychain, Android Keystore (never localStorage) |
| **PKCE** | Always use S256 challenge method |
| **State parameter** | 128+ bits entropy, validate on callback |
| **Audience validation** | Verify `aud` parameter matches FHIR server |
| **Refresh rotation** | For public clients, rotate refresh tokens |

### Epic-Specific Considerations

1. **Device binding (May 2022+):** Public apps use public-private key cryptography for device-specific binding
2. **Asymmetric auth:** Confidential clients should use private key JWT instead of client secrets
3. **Per-site variance:** OAuth endpoints are Epic-instance specific
4. **Scope validation:** Epic enforces strict scope validation
5. **Context parameters:** Epic returns `patient`, `encounter`, `fhirUser` in token response

### Implementation for Open Wearables

To integrate with Epic, Open Wearables would need:

1. **SMART on FHIR client library** - Handle OAuth flow, token refresh
2. **FHIR resource mapping** - Convert internal models to FHIR Observations
3. **EHR launch handler** - Accept launch context from Epic
4. **Standalone launch flow** - For patient-facing mobile app
5. **Token storage** - Secure storage for Epic access/refresh tokens

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Recovery Companion App                        │
│                                                                   │
│  ┌─────────────────┐    ┌─────────────────┐                     │
│  │ OpenWearables   │    │ SMART on FHIR   │                     │
│  │ Service         │    │ Client          │                     │
│  │ (current)       │    │ (new)           │                     │
│  └────────┬────────┘    └────────┬────────┘                     │
│           │                      │                               │
│           │    ┌─────────────────┼─────────────────┐            │
│           │    │                 │                 │            │
│           ▼    ▼                 ▼                 ▼            │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │ Open Wearables  │    │ Epic FHIR API   │    │ Local       │ │
│  │ Backend         │    │                 │    │ Storage     │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Resources

### Official Epic Resources

- [Epic Vendor Services](https://vendorservices.epic.com/)
- [Epic Showroom](https://showroom.epic.com/)
- [Open.epic (Free sandbox)](https://open.epic.com)

### FHIR & SMART on FHIR Documentation

- [HL7 FHIR R4 Specification](https://hl7.org/fhir/R4/)
- [FHIR Observation Resource](https://hl7.org/fhir/R4/observation.html)
- [FHIR Observation Examples](https://hl7.org/fhir/R4/observation-examples.html)
- [FHIR Vital Signs Profile](https://www.hl7.org/fhir/observation-vitalsigns.html)
- [US Core Heart Rate Profile](https://build.fhir.org/ig/HL7/US-Core/StructureDefinition-us-core-heart-rate.html)
- [Physical Activity Implementation Guide](https://build.fhir.org/ig/HL7/physical-activity/measures.html)
- [SMART on FHIR Documentation](https://docs.smarthealthit.org/)
- [SMART App Launch v2.2.0](https://www.hl7.org/fhir/smart-app-launch/app-launch.html)
- [SMART on FHIR OAuth 2.0 Guide - Censinet](https://censinet.com/perspectives/smart-on-fhir-oauth-2-0-implementation-guide)

### LOINC Codes

- [LOINC 8867-4 (Heart Rate)](https://loinc.org/8867-4)
- [LOINC 80404-7 (HRV - SDNN)](https://loinc.org/80404-7)
- [LOINC 41950-7 (Steps 24h)](https://loinc.org/41950-7)
- [LOINC 55423-8 (Steps Pedometer)](https://loinc.org/55423-8)
- [LOINC 93832-4 (Sleep Duration)](https://loinc.org/93832-4)
- [LOINC 85353-1 (Vital Signs Panel)](https://loinc.org/85353-1)
- [LOINC Exercise/Activity Group](https://loinc.org/LG41761-4)

### Wearable Data & FHIR Research

- [Wearable Data Integration with FHIR - Frontiers](https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2025.1636775/full)
- [Integrating Garmin Data into FHIR - PubMed](https://pubmed.ncbi.nlm.nih.gov/41041771/)
- [Wearable Data Mapping to FHIR - ResearchGate](https://www.researchgate.net/publication/371960952_Wearable_Device_Health_Data_Mapping_to_Open_mHealth_and_FHIR_Data_Formats)
- [Wearables & FHIR - Health Samurai](https://www.health-samurai.io/articles/aidbox-for-wearable-and-medical-devices)

### Industry Guides

- [Epic EHR Integration Guide 2026 - Taction](https://www.tactionsoft.com/blog/epic-ehr-integration-guide/)
- [SMART on FHIR App Development Tutorial - Taction](https://www.tactionsoft.com/blog/smart-on-fhir-app-development-tutorial/)
- [What is Epic Vendor Services? - 6b.health](https://6b.health/insight/what-is-epic-vendor-services/)
- [An Epic Tale: The Startup Odyssey - Health API Guy](https://healthapiguy.substack.com/p/an-epic-saga-the-startup-odyssey)
- [What is the Epic Showroom? - VectorCare](https://vectorcare.dev/learn/what-is-the-epic-showroom)

---

## Next Steps

1. Review this document with stakeholders
2. Decide on integration pathway (embedded app vs. data pipeline)
3. Begin SOC 2 preparation
4. Register for Epic Vendor Services
5. Identify potential pilot customers

---

*Document created: August 2026*
*Last updated: August 2026*
