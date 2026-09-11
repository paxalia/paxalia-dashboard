# analytics/data_import.py
"""
Historical data import for people migrating in from Google Analytics
or Plausible — deliberately CSV-based, not a live API integration.

WHY CSV, NOT THE GA4 API: a real GA4 API integration needs OAuth
credentials, a Google API client library dependency, and per-property
configuration this package has no way to own (same category of
problem as billing/Celery — it isn't this package's data). A CSV
export, by contrast, needs nothing but a file the person already has
(GA4's UI and Plausible's Settings > Imports & Export page both offer
one) and no new dependency. This is a deliberate scope decision, not
a shortcut: it trades "fully automated" for "works today, no
credentials, no new dependency."

WHY ONE PARSER FOR BOTH SOURCES: despite the different UIs, a GA4
daily-metrics export and a Plausible CSV export are both, at heart, a
table with a date column and a handful of aggregate metric columns —
they don't need two bespoke parsers, just column-name recognition
across both vocabularies (GA says "Views"/"Sessions"/"Users",
Plausible says "pageviews"/"visitors"). GA's exports also carry a
few leading metadata/title lines before the real header row (e.g.
"# Traffic acquisition" / a date-range line) — _find_header_row()
skips anything before the first row that looks like a real header.

SCOPE: only date + aggregate-metric CSVs (one row per day) are
supported — feeding this a page-level or dimension-broken-down export
(e.g. GA's "Pages and screens" report, which has one row per URL, not
per day) won't produce useful results, since there's no per-page
target to import into for a plain daily-aggregate row. Historical
data lands in DailySiteStats, not PageView — there's no way to
reconstruct individual historical hits from an aggregate export, so
this doesn't try to.

METRIC MAPPING (documented, not guessed silently):
    views/pageviews    -> DailySiteStats.total_views
    visitors/users     -> DailySiteStats.unique_ips (closest available
                          field — GA's "Users"/Plausible's "visitors"
                          aren't literally unique IP counts, but
                          unique_ips is what this package's own daily
                          aggregation populates from real traffic, so
                          it's the closest semantic match)
    sessions           -> DailySiteStats.total_sessions
    bounce rate (%)    -> DailySiteStats.bounces, computed as
                          round(bounce_rate/100 * sessions) when both
                          are present; left at 0 otherwise
Anything this package can't derive from a generic export — unique_users
(as distinct from unique_ips), api_calls, top_pages, bot_views — is
left at 0/empty on imported rows rather than guessed.
"""
import csv
import io
from datetime import datetime

from .models import DailySiteStats

_DATE_ALIASES = {'date', 'day', 'nth day'}
_VIEWS_ALIASES = {'pageviews', 'views', 'screen page views', 'page views', 'page_views'}
_VISITORS_ALIASES = {'visitors', 'users', 'total users', 'unique visitors'}
_SESSIONS_ALIASES = {'sessions', 'total sessions'}
_BOUNCE_RATE_ALIASES = {'bounce rate', 'bounce_rate'}

_DATE_FORMATS = ('%Y-%m-%d', '%Y%m%d', '%m/%d/%Y', '%d/%m/%Y')


def _normalize_header(name):
    return name.strip().lower()


def _parse_date(value):
    value = (value or '').strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_number(value):
    if value is None:
        return None
    value = str(value).strip().replace(',', '').rstrip('%')
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _find_header_row(reader):
    """
    Return (header_cells, remaining_rows) — skips any leading rows
    (GA's title/date-range metadata lines, blank lines) until it finds
    one containing a recognized date-column name. Returns (None, [])
    if nothing looks like a header anywhere in the file.
    """
    rows = list(reader)
    for i, row in enumerate(rows):
        normalized = {_normalize_header(c) for c in row}
        if normalized & _DATE_ALIASES:
            return row, rows[i + 1:]
    return None, []


def parse_analytics_csv(file_text):
    """
    Returns (rows, warnings). Each row in `rows` is a dict:
        {'date': date, 'views': float|None, 'visitors': float|None,
         'sessions': float|None, 'bounce_rate_pct': float|None}
    `warnings` is a list of human-readable strings for anything
    skipped — an unparseable date, a completely empty line, etc. —
    never an exception; a malformed row is a warning, not a failure
    of the whole import.
    """
    reader = csv.reader(io.StringIO(file_text))
    header, data_rows = _find_header_row(reader)
    warnings = []

    if header is None:
        return [], ["Couldn't find a header row with a recognizable date column. "
                     "Expected one of: " + ', '.join(sorted(_DATE_ALIASES))]

    normalized_header = [_normalize_header(c) for c in header]
    col_index = {}
    for idx, col in enumerate(normalized_header):
        if col in _DATE_ALIASES and 'date' not in col_index:
            col_index['date'] = idx
        elif col in _VIEWS_ALIASES and 'views' not in col_index:
            col_index['views'] = idx
        elif col in _VISITORS_ALIASES and 'visitors' not in col_index:
            col_index['visitors'] = idx
        elif col in _SESSIONS_ALIASES and 'sessions' not in col_index:
            col_index['sessions'] = idx
        elif col in _BOUNCE_RATE_ALIASES and 'bounce_rate' not in col_index:
            col_index['bounce_rate'] = idx

    if 'date' not in col_index:
        return [], ["Header row found but no date column matched — this shouldn't happen; please report it."]

    def cell(row, key):
        idx = col_index.get(key)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    rows = []
    for line_num, row in enumerate(data_rows, start=1):
        if not row or not any(c.strip() for c in row):
            continue  # blank line — common as a GA export footer
        parsed_date = _parse_date(cell(row, 'date'))
        if parsed_date is None:
            warnings.append(f"Row {line_num}: couldn't parse a date from '{cell(row, 'date')}' — skipped.")
            continue

        bounce_raw = _parse_number(cell(row, 'bounce_rate'))
        rows.append({
            'date': parsed_date,
            'views': _parse_number(cell(row, 'views')),
            'visitors': _parse_number(cell(row, 'visitors')),
            'sessions': _parse_number(cell(row, 'sessions')),
            'bounce_rate_pct': bounce_raw,
        })

    if not rows:
        warnings.append("No usable data rows found after the header.")

    return rows, warnings


def import_daily_stats(rows, site=None, source='csv', overwrite=False):
    """
    Writes parsed rows into DailySiteStats. A date that already has a
    row for this site is SKIPPED unless overwrite=True — historical
    import is meant to fill in days before this package was tracking,
    not to silently clobber real tracked data that happens to overlap.

    Returns {'created': int, 'updated': int, 'skipped_existing': int}.
    """
    summary = {'created': 0, 'updated': 0, 'skipped_existing': 0}

    for row in rows:
        existing = DailySiteStats.objects.filter(site=site, date=row['date']).first()
        if existing is not None and not overwrite:
            summary['skipped_existing'] += 1
            continue

        views = int(row['views']) if row['views'] is not None else 0
        visitors = int(row['visitors']) if row['visitors'] is not None else 0
        sessions = int(row['sessions']) if row['sessions'] is not None else 0
        bounces = 0
        if row['bounce_rate_pct'] is not None and sessions:
            bounces = round(row['bounce_rate_pct'] / 100 * sessions)

        defaults = {
            'total_views': views,
            'unique_ips': visitors,
            'total_sessions': sessions,
            'bounces': bounces,
            'imported_from': source,
        }

        if existing is not None:
            for key, value in defaults.items():
                setattr(existing, key, value)
            existing.save(update_fields=list(defaults.keys()))
            summary['updated'] += 1
        else:
            DailySiteStats.objects.create(site=site, date=row['date'], **defaults)
            summary['created'] += 1

    return summary
