"""Free keyword-overlap ranking. No API calls.

This exists as an overflow valve, not as a scorer. When a run turns up more
pre-filter survivors than ``max_triage_per_run``, something has to decide which
ones get paid LLM triage -- and picking by arrival order would be arbitrary.
Overlap with Chris's actual skill set is a far better tiebreak, and it costs
nothing.

It is deliberately *not* used to reject anything. A low overlap score only means
"triage this one later", never "hide this one".
"""
import re
from datetime import timedelta

from django.utils import timezone

_WORD = re.compile(r'[a-z0-9+#.]+')

# Overlap in the title is worth far more than a passing mention in a benefits
# paragraph, so title and body are scored separately and weighted.
TITLE_WEIGHT = 6.0
BODY_WEIGHT = 1.0
MUST_HAVE_WEIGHT = 4.0
RECENCY_MAX = 12.0
SALARY_BONUS = 4.0


def _tokens(text):
    return set(_WORD.findall((text or '').lower()))


def build_vocabulary(profile, master_resume):
    """Skill terms worth matching on, with per-term weights.

    Drawn from the master resume's own keywords so the ranking reflects what Chris
    actually does, rather than a list someone hand-maintained.
    """
    vocab = {}
    for keyword in (master_resume or {}).get('keywords', []):
        name = (keyword.get('name') or '').lower().strip()
        if name:
            vocab[name] = 1.0
    for term in (profile.nice_to_have or []):
        term = (term or '').lower().strip()
        if term:
            vocab[term] = max(vocab.get(term, 0), 1.5)
    for term in (profile.must_have or []):
        term = (term or '').lower().strip()
        if term:
            vocab[term] = MUST_HAVE_WEIGHT
    return vocab


def _hits(text, vocabulary):
    """Weighted count of vocabulary terms present in ``text``.

    Multi-word terms ('rest api') are matched as substrings; single words are
    matched against the token set so 'go' doesn't fire inside 'category'.
    """
    if not text:
        return 0.0, []
    low = text.lower()
    tokens = _tokens(low)
    total, matched = 0.0, []
    for term, weight in vocabulary.items():
        present = (term in low) if ' ' in term else (term in tokens)
        if present:
            total += weight
            matched.append(term)
    return total, matched


def overlap_score(posting, vocabulary, now=None):
    """0-100 heuristic. Higher means 'more worth spending a triage call on'."""
    now = now or timezone.now()

    title_score, title_terms = _hits(posting.title, vocabulary)
    body_score, body_terms = _hits((posting.description_text or '')[:12000], vocabulary)

    raw = title_score * TITLE_WEIGHT + body_score * BODY_WEIGHT

    # Fresh postings are worth more: they are less likely to be already filled.
    if posting.posted_at:
        age_days = max(0.0, (now - posting.posted_at).total_seconds() / 86400)
        raw += RECENCY_MAX * max(0.0, 1 - age_days / 30)

    # A stated salary is a small quality signal -- and makes the card more useful.
    if posting.salary_max:
        raw += SALARY_BONUS

    # Squash to 0-100. The divisor is tuned so a strong match lands near 80-95
    # rather than pinning everything at 100.
    score = 100 * raw / (raw + 45)
    return round(score, 1), sorted(set(title_terms) | set(body_terms))


def rank(postings, profile, master_resume, limit=None):
    """Order postings best-first by free overlap score. Never drops anything."""
    vocabulary = build_vocabulary(profile, master_resume)
    now = timezone.now()
    scored = []
    for posting in postings:
        score, terms = overlap_score(posting, vocabulary, now)
        scored.append((score, terms, posting))
    scored.sort(key=lambda row: row[0], reverse=True)
    return scored[:limit] if limit else scored
