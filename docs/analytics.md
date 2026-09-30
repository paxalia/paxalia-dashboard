---

# Custom Event Tracking

Track product interactions without adding another analytics provider.

### Quick start

Use the bundled event script:

```html

<script src="{% static 'paxalia/scripts/analytics-events.js' %}"></script>
```

The host project should ensure the script receives the appropriate CSP nonce when a strict CSP requires one.

### Data attributes

```html

<button
        data-analytics-category="download"
        data-analytics-action="click"
        data-analytics-label="windows">
    Download for Windows
</button>
```

Forms can use the same mechanism:

```html

<form
        data-analytics-category="form"
        data-analytics-action="submit"
        data-analytics-label="contact-form">
    ...
</form>
```

### JavaScript API

```javascript
window.opAnalytics(
    "video",
    "play",
    "intro-tutorial",
    1
);
```

### Event fields

| Field      | Required | Description                                           |
|------------|----------|-------------------------------------------------------|
| `category` | Yes      | Broad grouping such as `button`, `video`, or `form`   |
| `action`   | Yes      | Event action such as `click`, `play`, or `submit`     |
| `label`    | No       | Additional event context                              |
| `value`    | No       | Optional numeric value                                |
| `path`     | No       | Page path, normally derived from the browser location |

---


---

## Advanced Analytics

### Goals

Goals represent target behaviors such as:

```text
/signup/
purchase
form:submit
```

and can be used to measure completion.

### Funnels

Funnels describe ordered steps such as:

```text
landing page
    ↓
pricing
    ↓
signup
    ↓
checkout
```

### Segments

Segments provide reusable audience definitions.

They can combine supported behavioral dimensions instead of forcing administrators to reproduce the same filters
manually.

### Campaigns

Campaign analysis works with campaign parameters and provides source/medium/campaign-oriented breakdowns.

### Cohorts

Cohort analysis focuses on return behavior over time rather than one aggregate visitor total.

### Annotations

Annotations connect events such as:

- deployments
- campaigns
- incidents
- launches
- operational changes

to the analytics timeline.

---


---

## Reporting & Sharing

### Scheduled reports

The reporting subsystem can schedule high-level dashboard summaries and deliver them through configured email workflows.

The package can also generate PDF output where the optional PDF dependency is available.

### Public share links

Protected read-only share links allow external stakeholders to view a selected dashboard surface without receiving staff
credentials.

These links are intended to be narrowly scoped and protected.

### Exports

Reporting workflows can generate:

- CSV
- JSON
- PDF, where configured

The reporting path reuses existing dashboard computation rather than maintaining a separate analytics calculation
engine.

---


---

## Exporting Data

Paxalia provides normal table exports throughout the dashboard.

### CSV

CSV is suitable for:

- Excel
- Google Sheets
- scripts
- operational review

### JSON

JSON is intended for:

- scripts
- integrations
- data inspection
- programmatic use

### Export context

Dashboard exports respect relevant filters such as:

- selected date range
- page/path search
- country selection
- current table/query context

Exports must not be interpreted as unrestricted database dumps.

### Spreadsheet safety

Administrative/logging exports are expected to use safe serialization for values that might otherwise be interpreted as
spreadsheet formulas.

---


---

## Multi-Site Analytics

Multiple domains can be represented by `Site` records.

Requests are resolved by hostname and associated with active sites.

Configure:

```python
PAXALIA_DASHBOARD = {
    "AUTO_CREATE_SITES": False,
}
```

Automatic site creation is disabled by default.

This avoids silently creating database rows for unexpected hostnames.

---
