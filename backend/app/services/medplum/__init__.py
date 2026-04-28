"""Medplum FHIR Integration Services.

This module provides integration with Medplum FHIR server for clinical data:
- Heart rate processing with anomaly detection and hourly aggregation
- Context detection (resting/active/sleeping/exercising)
- Webhook delivery to Medplum FHIR Conversion Bot
"""

from app.services.medplum.hr_processor import HRContext, HRProcessor, HRReading, HRThresholds
from app.services.medplum.context_detector import ContextDetector
from app.services.medplum.webhook import MedplumWebhook

__all__ = [
    "HRContext",
    "HRProcessor",
    "HRReading",
    "HRThresholds",
    "ContextDetector",
    "MedplumWebhook",
]
