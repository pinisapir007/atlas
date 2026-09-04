"""Canonical metadata for durable ATLAS observations.

A PageObservation is transient sensor output. A Finding is the durable
knowledge record. This module preserves the observation-time identity
needed for longitudinal learning without creating a second memory system.
"""

import hashlib
import json

from atlas.brain.models import now
from atlas.integrations.base import PageObservation


def observation_observed_at(observation: PageObservation) -> str:
    """Return the real sensor timestamp when available.

    Existing sensors currently leave fetched_at empty, so the honest
    fallback is the instant immediately after observation completes,
    never an invented historical timestamp.
    """
    return observation.fetched_at or now()


def observation_content_hash(observation: PageObservation) -> str:
    """Stable SHA-256 fingerprint of the real observed content.

    Timestamp is deliberately excluded: re-reading unchanged content
    should produce the same hash; a real content change should not.
    """
    payload = {
        "url": observation.url,
        "title": observation.title,
        "text_content": observation.text_content,
        "structured_data": observation.structured_data,
        "text_segments": [
            {
                "locator_prefix": segment.locator_prefix,
                "text": segment.text,
            }
            for segment in observation.text_segments
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
