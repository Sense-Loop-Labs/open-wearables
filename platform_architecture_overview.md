# Open Wearables - Architecture Overview

*For non-technical stakeholders*

---

## What Is Open Wearables?

**Open Wearables** is a platform that collects health data from wearable devices (Apple Watch, Garmin, Fitbit, Oura, Whoop, etc.) and makes it available through a single, unified system.

Instead of building separate connections to each wearable brand, apps can use Open Wearables to:
- Connect to any supported wearable device
- Access health data in a consistent format
- Build health applications without worrying about device differences

Think of it as a **universal translator** for wearable health data.

---

## How It Works (Simple View)

```
┌─────────────────────────────────────────────────────────────┐
│                     WEARABLE DEVICES                        │
│  Apple Watch  •  Garmin  •  Fitbit  •  Oura  •  Whoop      │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   OPEN WEARABLES                            │
│                                                             │
│  • Collects data from all devices                          │
│  • Normalizes into consistent format                       │
│  • Stores securely in database                             │
│  • Provides API for apps to access                         │
│                                                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    YOUR APPLICATIONS                        │
│  Recovery Companion  •  Patient Dashboards  •  Analytics   │
└─────────────────────────────────────────────────────────────┘
```

---

## What Health Data Is Collected?

| Category | Data Types |
|----------|------------|
| **Heart** | Heart rate, resting heart rate, HRV (stress/recovery indicator) |
| **Activity** | Steps, calories burned, exercise minutes, workouts |
| **Sleep** | Duration, quality, sleep stages (deep, light, REM) |
| **Body** | Weight, temperature, blood pressure, oxygen saturation |
| **Scores** | Sleep score, recovery score, readiness score |

---

## Supported Wearable Devices

### Cloud-Connected (OAuth)
These devices sync to their own cloud, and we pull data from there:
- **Garmin** (watches, fitness trackers)
- **Fitbit** (watches, trackers)
- **Oura** (ring)
- **Whoop** (band)
- **Polar** (watches)
- **Strava** (app, imports from other devices)

### Device-Direct (Mobile SDK)
These sync directly from the phone/watch to our system:
- **Apple Watch** (via HealthKit)
- **Samsung Galaxy Watch** (via Samsung Health)
- **Google Pixel Watch** (via Health Connect)

---

## Key Components

### 1. Backend API
The brain of the system. Handles:
- User accounts and authentication
- Connections to wearable providers
- Data storage and retrieval
- Syncing health data on schedule

### 2. Mobile SDKs
Code libraries for iOS and Android apps:
- **iOS SDK** (Swift) - for Apple Watch data
- **Android SDK** (Kotlin) - for Samsung/Google watches
- **React Native SDK** - for cross-platform apps

### 3. Developer Dashboard
A web portal where developers can:
- Manage API credentials
- View connected users
- Monitor data sync status

### 4. Background Workers
Automated processes that:
- Pull data from wearable clouds every hour
- Process incoming webhook notifications
- Send alerts when health anomalies detected

---

## Security & Privacy

| Feature | Description |
|---------|-------------|
| **Self-Hosted** | You control where data is stored |
| **Encrypted** | All data encrypted in transit and at rest |
| **HIPAA Ready** | Audit logging enabled, 7-year retention |
| **Access Control** | Fine-grained permissions per user/app |

---

## Integration with Healthcare Systems

Open Wearables connects to **Medplum** (our FHIR healthcare platform):

```
Open Wearables  ──────►  Medplum  ──────►  Clinical Applications
   (Raw Data)           (FHIR Format)      (Patient Dashboards)
```

This allows health data to be:
- Converted to medical-standard format (FHIR)
- Linked to patient records
- Used by clinicians for monitoring

---

## Infrastructure (Where It Runs)

Deployed on **Amazon Web Services (AWS)**:

| Component | Purpose | Cost Impact |
|-----------|---------|-------------|
| API Server | Handles requests from apps | ~$40/month |
| Database | Stores all health data | ~$35/month |
| Cache | Speeds up data access | ~$25/month |
| Background Workers | Syncs data automatically | ~$30/month |

**Total staging cost: ~$130-150/month**
**Production cost: ~$250-350/month** (with redundancy)

---

## How Apps Use Open Wearables

### Example: Recovery Companion App

1. **Patient opens app** → App requests health data from Open Wearables
2. **Open Wearables checks** → Pulls latest from Apple Watch via SDK
3. **Data returned** → Heart rate, sleep, activity for past 7 days
4. **App displays** → Dashboard with vitals and trends

### Example: Clinician Dashboard

1. **Doctor opens portal** → Requests patient health summary
2. **Open Wearables queries** → Aggregates data from all connected devices
3. **Data returned** → Week of health metrics in FHIR format
4. **Dashboard displays** → Trends, alerts, anomalies

---

## Summary

**Open Wearables is the data pipeline** that:

✓ Connects to 10+ wearable device brands
✓ Normalizes data into consistent format
✓ Stores securely with HIPAA compliance
✓ Provides API for health applications
✓ Integrates with clinical systems (Medplum)
✓ Runs automatically in the background

It's the foundation that makes Recovery Companion and other health apps possible.
