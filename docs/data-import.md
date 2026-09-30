# Paxalia Historical Data Import

## Overview

Paxalia provides historical aggregate-data import for analytics sources without requiring vendor OAuth credentials.

The current feature supports CSV-oriented import workflows for Google Analytics and Plausible aggregate exports.

Dashboard route:

```text
/import/
```

## Why aggregate import

The import feature is designed for historical continuity rather than live vendor synchronization.

The typical workflow is:

```text
export aggregate data from source
        ↓
upload CSV
        ↓
validate/parse
        ↓
map supported metrics
        ↓
import historical records
```

## Supported sources

The current package documentation/source includes:

- Google Analytics aggregate CSV
- Plausible aggregate CSV

The importer does not require the host application to hand Paxalia a third-party OAuth credential simply to import an exported history file.

## Size limits

Host configuration controls the maximum uploaded data-import file size:

```python
PAXALIA_DASHBOARD = {
    "DATA_IMPORT_MAX_FILE_SIZE_MB": 100,
}
```

The normal Paxalia upload subsystem is also bounded.

## Data mapping

Import operates on supported aggregate fields rather than pretending to reconstruct every vendor-specific raw event.

Existing dates/periods are mapped into Paxalia's analytics model according to the source adapter.

The importer should reject malformed/unsupported input rather than silently guessing metric meaning.

## Relationship to live analytics

Imported historical data exists to preserve useful historical continuity. It does not replace the normal Paxalia event/page-view pipeline used after installation.

## Security

Uploaded CSVs must be treated as untrusted input. Validation and size limits are part of the import boundary.

Do not use imported CSV data as a way to bypass the normal authorization, CSRF, or upload safety controls.

## Related documentation

- [Analytics](analytics.md)
- [Configuration](configuration.md)
- [Operations](operations.md)
