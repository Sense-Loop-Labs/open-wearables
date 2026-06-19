"""HR Analysis Services.

This module provides heart rate analysis for clinical alerting:
- Heart rate processing with anomaly detection
- Context detection (resting/active/sleeping/exercising)
- Anomaly recording for Sense Loop alerts
"""

from app.services.medplum.hr_processor import HRContext, HRProcessor, HRReading, HRThresholds
from app.services.medplum.context_detector import ContextDetector

__all__ = [
    "HRContext",
    "HRProcessor",
    "HRReading",
    "HRThresholds",
    "ContextDetector",
]
