"""Application-layer security primitives for the scraper pipeline.

Currently exposes the indirect prompt-injection scanner used to flag untrusted
scraped event content before it reaches the LLM annotator (Security Hardening
Plan v16, Phase 0 / Phase 1).
"""

from security.injection_guard import (
    InjectionHit,
    finding_fingerprint,
    max_severity,
    scan_for_injection,
)

__all__ = [
    "InjectionHit",
    "scan_for_injection",
    "finding_fingerprint",
    "max_severity",
]
