---

# Paxalia Package Format

`.paxalia` is a model-aware logical package format.

It is **not** a raw database dump.

Conceptually:

```text
ordinary package

package.paxalia
├── manifest.json
├── integrity.json
└── data.json
```

and an encrypted package can use the encrypted data member:

```text
package.paxalia
├── manifest.json
├── integrity.json
└── data.enc
```

The exact package internals are versioned by the package format itself.

### Manifest

The manifest records package metadata required for validation and compatibility.

It allows the reader to establish:

- package format version
- logical package metadata
- model scope
- object/relationship context
- translation information where included
- encryption state

### Integrity

Package contents are integrity-checked with SHA-256 hashes.

Tampered package data must fail validation.

### Archive safety

The package reader validates archive structure before database mutation.

Security checks include defenses for:

- duplicate ZIP members
- path traversal
- invalid archive structure
- unsupported versions
- invalid encryption metadata
- size/count limits
- malformed records
- malformed relationships

The package file extension itself is not treated as a security boundary.

### Serialization

The exporter handles supported Django/Python values such as:

- UUID
- datetime
- date
- time
- Decimal
- timedelta
- Path
- bytes
- JSON-compatible structures
- Django `FieldFile` logical paths
- lazy translation values
- relationship identities

The serializer does not blindly call `json.dumps()` on arbitrary model values.

Unsupported or unexpected data is treated as an explicit export problem where required rather than silently presented as
a complete successful package.

### Identity resolution

Imports use configured identity fields where appropriate.

Examples include:

- primary key
- unique field
- slug
- username
- email
- configured field combinations

Identity resolution occurs before relationship restoration.

New records normally receive new Django IDs unless the package strategy explicitly requires identity restoration.

### Relationships

Paxalia packages can preserve supported:

- ForeignKey relationships
- OneToOne relationships
- ManyToMany relationships
- self-references
- supported translation relationships

Relationship restoration is identity-aware and does not depend on archive row order.

### Conflicts

The current default allowed strategies are:

```text
update
skip
```

The package engine validates the selected conflict strategy against configured policy.

### Import preview

The Import workflow can preview:

- model count
- record count
- creates
- updates
- skips
- potential failures
- relationships
- translations
- encryption state
- validation state

The preview is generated from actual package validation and planning.

It is not an illustrative hard-coded result.

### Dry run

A dry run validates and plans without permanent database mutation.

It can detect:

- malformed records
- identity conflicts
- missing relationships
- incompatible fields
- translation problems
- permissions
- size/count limits
- encryption requirements

### Atomic imports

Atomic import uses Django transactions according to the configured scope.

If required work fails, the configured transaction boundary can roll back mutations.

### Partial imports

Partial import allows independent valid work to remain committed while failed work is isolated and reported.

A relationship-dependent operation should not be called a successful partial import when the dependency graph makes the
resulting data invalid.

### Failure reporting

Failures are structured around:

- model
- object identity
- field
- relationship
- translation
- exception category
- safe failure reason

Secret material should not be included.

### Retry packages

Failed subsets can be packaged for retry where practical.

The retry package preserves the relevant operation context without forcing an administrator to reconstruct the failed
data manually.

### Protected models

Configured protected models can require encryption:

```python
PAXALIA_DASHBOARD = {
    "PACKAGE_REQUIRE_ENCRYPTION_FOR_PROTECTED": True,
}
```

This policy is enforced by the package engine, not only by the UI.

### Encryption

Paxalia package encryption uses authenticated encryption via the optional `cryptography` dependency.

The current security module uses:

```text
AES-256-GCM
PBKDF2-HMAC-SHA256
```

with bounded/validated KDF parameters.

Wrong passwords and tampering produce package-security failures rather than partial plaintext processing.

### Package limits

Current defaults include:

```python
PAXALIA_DASHBOARD = {
    "PACKAGE_MAX_FILE_SIZE_MB": 100,
    "PACKAGE_MAX_OBJECTS": 10000,
    "PACKAGE_MAX_RELATIONS": 50000,
}
```

These limits are intended to keep administrative package operations predictable.

### CLI validation

Validate:

```bash
python manage.py paxalia_package_validate export.paxalia
```

Inspect:

```bash
python manage.py paxalia_package_inspect export.paxalia
```

Encrypted package inspection requires the appropriate password input according to the command's options.

### Important distinction: package vs backup

Use **physical backups** for:

- disaster recovery
- database restoration
- server recovery
- infrastructure migration
- full system restore

Use **`.paxalia` packages** for:

- logical application-data transfer
- selected model migration
- model-aware export/import
- translation transfer
- environment-to-environment content movement
- controlled administrative data exchange

Do not use a logical package as your only disaster-recovery mechanism.

---
