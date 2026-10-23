"""SYSTEM_PROMPT publication rules (ndl-relevance-publication, Phase D / C4)."""

import re

from annotator import SYSTEM_PROMPT


def _event_form_candidates() -> list[str]:
    block = SYSTEM_PROMPT.split("EVENT FORM RULES:", 1)[1].split("Decision guides:", 1)[0]
    listed = block.split("Pick one or more from:", 1)[1]
    return [v.strip() for v in re.split(r"[,\s]+", listed) if v.strip()]


def test_event_form_candidate_list_excludes_publication():
    candidates = _event_form_candidates()
    assert "exhibition" in candidates
    assert "publication" not in candidates


def test_publication_decision_guide_is_a_single_prohibition():
    assert 'Never output "publication": the pipeline assigns it to bibliographic records.' in SYSTEM_PROMPT
    assert '"publication" is ONLY for publication metadata' not in SYSTEM_PROMPT
    assert 'must not include "publication"' not in SYSTEM_PROMPT


def test_frozen_publication_sections_present():
    assert "PUBLICATION RECORDS (only when the line `RECORD_TYPE: publication` precedes the data block)" in SYSTEM_PROMPT
    assert "PUBLICATION RECORDS — FIELD RULES" in SYSTEM_PROMPT
    assert SYSTEM_PROMPT.index("PUBLICATION RECORDS (only") < SYSTEM_PROMPT.index("LOCATION GATE")
