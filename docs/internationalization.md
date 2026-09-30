---

# Internationalization

The current distribution includes translations for:

| Language             | Code      | RTL |
|----------------------|-----------|-----|
| English              | `en`      | No  |
| Spanish              | `es`      | No  |
| Arabic               | `ar`      | Yes |
| Simplified Chinese   | `zh-hans` | No  |
| Brazilian Portuguese | `pt-br`   | No  |

Arabic uses RTL layout direction.

The language system is based on Django's standard internationalization workflow.

### Adding another language

A normal workflow is:

```bash
mkdir -p paxalia/locale/<code>/LC_MESSAGES
```

Then add/translate the corresponding `.po` file and compile:

```bash
python manage.py compilemessages -l <code>
```

The generic dashboard uses Django translation tags rather than hard-coded per-language template branches.

### Admin localization

Paxalia Admin's model localization workspace is different from the dashboard UI translation catalog.

For model translation data:

- supported languages are discovered from Django configuration
- translation systems are discovered from model metadata
- supported translation APIs are reused
- missing translations are identified
- translations can be edited where the model exposes a supported editing surface
- package import/export can carry multilingual translation data

There is no six-language hard-coded Admin branch.

---
