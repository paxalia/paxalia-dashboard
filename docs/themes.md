---

# Themes

The current dashboard ships with twelve themes.

| Theme            | Slug       | Character                   |
|------------------|------------|-----------------------------|
| Dark Gold        | `dark`     | Deep charcoal and warm gold |
| Skybound Silk    | `default`  | Soft light presentation     |
| Golden Dusk      | `golden`   | Cream and gold              |
| Azure Drift      | `azure`    | Cool blue                   |
| Sunlit Meadow    | `sunlit`   | Bright green                |
| Indigo Spectrum  | `indigo`   | Violet night                |
| Arctic Horizon   | `arctic`   | Icy blue                    |
| Ocean Breeze     | `ocean`    | Teal and navy               |
| Twilight Reverie | `twilight` | Deep violet                 |
| Velvet Noir      | `velvet`   | Crimson / dark              |
| Citrine Prestige | `citrine`  | Gold-forward                |
| Onyx Pearl       | `onyx`     | Minimal dark / silver       |

### Theme contract

Themes are applied using the existing:

```html
data-analytics-theme="..."
```

contract and the shared `--analytics-*` token vocabulary.

### Persistence

The selected theme is persisted in browser storage.

### Custom themes

Add a new theme selector to the existing theme stylesheet:

```css
[data-analytics-theme="your-slug"] {
    --analytics-bg: # . . .;
    --analytics-surface: # . . .;
    --analytics-border: # . . .;
    --analytics-text: # . . .;
    --analytics-text-dim: # . . .;
    --analytics-gold: # . . .;
    --analytics-gold-dim: rgba(...);
    --analytics-gold-hover: # . . .;
    --analytics-compare: # . . .;
}
```

Then expose it through the settings theme list.

Do not introduce a second theme system.

---
