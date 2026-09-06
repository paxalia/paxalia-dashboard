# analytics/segments.py
"""
Applies a Segment's saved filters to a PageView queryset.

Only fields in ALLOWED_FILTER_FIELDS can be filtered on — Segment.filters
is a JSON dict edited via a form, not a raw query, so this allowlist is
what keeps it from becoming an arbitrary-field(or worse, arbitrary
lookup) injection surface. Extend the allowlist deliberately, not by
just accepting whatever key shows up in the JSON.
"""

ALLOWED_FILTER_FIELDS = {
    'country_code', 'city', 'path', 'utm_source', 'utm_medium', 'utm_campaign',
}
# NOTE: device/browser/os are deliberately NOT here — PageView doesn't
# store them as columns (they're parsed from user_agent on the fly in
# traffic.py), so filtering on them isn't a plain field lookup. Add
# them once/if that data gets its own stored fields.


def segment_scoped(queryset, segment):
    """Apply segment.filters to queryset as an AND of exact-match
    filters, ignoring any key not in ALLOWED_FILTER_FIELDS. Returns the
    queryset unchanged if segment is None."""
    if segment is None or not segment.filters:
        return queryset
    safe_filters = {
        key: value for key, value in segment.filters.items()
        if key in ALLOWED_FILTER_FIELDS and value not in (None, '')
    }
    return queryset.filter(**safe_filters) if safe_filters else queryset
