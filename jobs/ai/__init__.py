"""LLM tiers. Tier 1 (triage) is cheap and automatic; tier 2 (tailoring) is
expensive and only ever runs when Chris clicks a button."""
from .client import MissingAPIKey, TAILOR_MODEL, TRIAGE_MODEL  # noqa: F401
