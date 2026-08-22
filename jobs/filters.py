"""Tier 0: the free, deterministic pre-filter.

This runs on every discovered posting and rejects most of them before an LLM ever
sees one. It is the reason triage costs about a dollar a month.

It is also the most dangerous part of the system, because it rejects *silently*.
An over-aggressive rule hides good jobs and looks exactly like a slow market. Two
deliberate defenses:

* Every rejection records a human-readable ``filter_reason`` and the posting is
  kept, never deleted -- ``/jobs/filtered/`` shows what was thrown away and why.
* Every rule biases toward letting things through. Unparseable salary passes.
  Ambiguous seniority passes. Unknown location on a remote role passes. The cost
  of a false pass is a fraction of a cent; the cost of a false reject is a job
  Chris never sees.
"""
import re

# Ordered low -> high. Titles that match none of these are simply "unknown" and pass.
SENIORITY_PATTERNS = [
    (0, 'intern', re.compile(r'\b(intern|internship|co-?op|apprentice|trainee)\b', re.I)),
    (1, 'junior', re.compile(r'\b(junior|jr\.?|entry[- ]level|new ?grad|graduate|associate)\b', re.I)),
    (2, 'mid', re.compile(r'\b(mid[- ]level|ii|2)\b', re.I)),
    (3, 'senior', re.compile(r'\b(senior|sr\.?|iii|3)\b', re.I)),
    (4, 'staff', re.compile(r'\b(staff)\b', re.I)),
    (5, 'principal', re.compile(r'\b(principal|distinguished|fellow)\b', re.I)),
    (6, 'director', re.compile(r'\b(director|vp|vice president|head of|chief|cto)\b', re.I)),
]
SENIORITY_LEVELS = {name: level for level, name, _ in SENIORITY_PATTERNS}

# Used to spot remote roles that are explicitly *not* open to the US.
# A title containing one of these is engineering work, full stop. It passes the
# title rule without needing to appear in the profile's whitelist -- the whitelist
# can never enumerate every real job title, and a miss there costs Chris a job.
ENGINEERING_TITLE = re.compile(
    r'\b(software|backend|back[- ]end|frontend|front[- ]end|full[- ]?stack|platform|'
    r'infrastructure|systems?|application|api|web|cloud|data|security|reliability|'
    r'devops|sre|integration)\b[\w /,&-]*\b(engineer|developer)\b'
    r'|\b(engineer|developer|programmer)\b[\w /,&-]*\b(software|backend|platform|'
    r'infrastructure|api|systems?|python|web)\b'
    r'|\bsoftware (engineer|developer)\b|\bswe\b|\bsite reliability\b', re.I)

# Locations that mean "somewhere in the US" rather than a specific metro. These
# pass, because a US-wide posting is either remote or spans offices that include NYC.
US_WIDE_LOCATION = re.compile(
    r'^(us|usa|u\.s\.a?\.?|united states( of america)?|nationwide|'
    r'us[- ]remote|remote[- ]us|remote \(us\)|americas|north america)$', re.I)

# Placeholders a board emits when it has no location. Unknown is not a mismatch.
PLACEHOLDER_LOCATION = re.compile(
    r'^(n/?a|-+|none|null|tbd|various|multiple( locations)?|any|unspecified|'
    r'flexible|worldwide|global|anywhere|remote)$', re.I)

US_SIGNALS = re.compile(
    r'\b(us|usa|u\.s\.|united states|america|americas|north america|nyc|new york|'
    r'anywhere|worldwide|global|est|pst|cst)\b', re.I)
NON_US_REGIONS = re.compile(
    r'\b(emea|apac|latam|europe|european|eu only|uk only|united kingdom|germany|'
    r'deutschland|france|spain|portugal|poland|india|canada|australia|toronto|'
    r'singapore|japan|brazil|argentina|mexico|nigeria|kenya|philippines|dublin|'
    r'ireland|london|berlin|munich|amsterdam|barcelona|lisbon|bengaluru)\b', re.I)


def detect_seniority(title):
    """Highest seniority signal in a title, or ``None`` when the title says nothing."""
    best = None
    for level, name, pattern in SENIORITY_PATTERNS:
        if pattern.search(title or ''):
            if best is None or level > best[0]:
                best = (level, name)
    return best


def _matches_any(haystack, needles):
    low = (haystack or '').lower()
    return any(n.lower().strip() in low for n in needles if n and n.strip())


def prefilter(posting, profile):
    """Return a rejection reason, or ``None`` to pass this posting through to triage.

    ``posting`` is anything with ``title``, ``company``, ``location``, ``is_remote``,
    ``salary_min``/``salary_max`` and ``description_text`` -- a ``RawPosting`` or a
    saved ``JobPosting`` both work.
    """
    if profile is None:
        return None

    title = posting.title or ''
    company = posting.company or ''
    location = posting.location or ''

    # 1. Excluded companies -- cheapest and most absolute.
    if profile.exclude_companies and _matches_any(company, profile.exclude_companies):
        return f'excluded company: {company}'

    # 2. Explicitly unwanted titles.
    if profile.title_exclusions:
        for term in profile.title_exclusions:
            if term and term.lower().strip() in title.lower():
                return f'title exclusion: "{term}"'

    # 3. Title must look like engineering work. An explicit whitelist match passes,
    #    but so does anything that reads as an engineering title -- no whitelist can
    #    enumerate every real job title, and a miss there costs Chris a job.
    if not ENGINEERING_TITLE.search(title):
        if profile.titles and not _matches_any(title, profile.titles):
            return 'title matches no target role'

    # 4. Seniority band. Unknown seniority always passes -- most titles say nothing.
    detected = detect_seniority(title)
    if detected:
        level, name = detected
        floor = SENIORITY_LEVELS.get((profile.seniority_floor or '').lower())
        ceiling = SENIORITY_LEVELS.get((profile.seniority_ceiling or '').lower())
        if floor is not None and level < floor:
            return f'seniority below floor: {name}'
        if ceiling is not None and level > ceiling:
            return f'seniority above ceiling: {name}'

    # 5. Salary. Only rejects when the posting *states* a max below the floor;
    #    an unstated or unparseable salary always passes.
    if profile.min_salary and posting.salary_max and posting.salary_max < profile.min_salary:
        return f'salary max ${posting.salary_max:,} below ${profile.min_salary:,}'

    # 6. Location.
    reason = _location_reason(posting, profile, location)
    if reason:
        return reason

    # 7. Description red flags -- last because it touches the most text.
    if profile.exclude_keywords:
        text = (posting.description_text or '')[:20000]
        for term in profile.exclude_keywords:
            if term and term.lower().strip() in text.lower():
                return f'excluded keyword: "{term}"'

    return None


def _location_reason(posting, profile, location):
    """Location rules, split out because they carry the most false-reject risk."""
    if posting.is_remote:
        if not profile.remote_ok:
            return 'remote not wanted'
        # A remote role naming only non-US regions isn't actually open to Chris.
        if location and NON_US_REGIONS.search(location) and not US_SIGNALS.search(location):
            return f'remote but not US-eligible: {location}'
        return None

    if profile.remote_only:
        return 'not remote'

    if not profile.locations:
        return None

    stripped = location.strip()
    if not stripped or PLACEHOLDER_LOCATION.match(stripped):
        # No usable location. Unknown is not a mismatch -- let triage read the posting.
        return None
    if US_WIDE_LOCATION.match(stripped):
        # "US" means remote or multi-office; either way Chris is eligible.
        return None
    if _matches_any(location, profile.locations):
        return None
    return f'location not targeted: {location}'
