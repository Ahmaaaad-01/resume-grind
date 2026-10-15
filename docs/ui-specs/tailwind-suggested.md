# Tailwind Configuration — Prediction Markets

## Overview

This project uses **Tailwind CSS v4** with CSS-based configuration (`@theme` directive in `globals.css`). There is no `tailwind.config.js` file. All customizations go into the CSS theme block.

---

## Recommended `globals.css` Theme Block

Replace the current `globals.css` `@theme` block and `:root` variables with the following. This is copy-paste ready.

```css
@import "tailwindcss";

/* ─── Design tokens as CSS custom properties ─── */
:root {
  --color-bg-primary:    #020617;
  --color-bg-surface:    #0F172A;
  --color-accent-500:    #38BDF8;
  --color-accent-600:    #0EA5E9;
  --color-text-heading:  #F8FAFC;
  --color-text-body:     #94A3B8;
  --color-border-subtle: rgba(255,255,255,0.08);

  --shadow-glow-sm:  0 0 10px rgba(56,189,248,0.08);
  --shadow-glow:     0 0 20px rgba(56,189,248,0.10), 0 0 60px rgba(56,189,248,0.05);
  --shadow-glow-lg:  0 0 30px rgba(56,189,248,0.15), 0 0 80px rgba(56,189,248,0.08);
  --shadow-surface:  0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3);
}

@theme inline {
  /* Backgrounds */
  --color-bg-primary:    var(--color-bg-primary);
  --color-bg-surface:    var(--color-bg-surface);

  /* Accent */
  --color-accent-500:    var(--color-accent-500);
  --color-accent-600:    var(--color-accent-600);

  /* Text */
  --color-text-heading:  var(--color-text-heading);
  --color-text-body:     var(--color-text-body);

  /* Border */
  --color-border-subtle: var(--color-border-subtle);

  /* Fonts */
  --font-sans: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
  --font-mono: 'Geist Mono', ui-monospace, SFMono-Regular, monospace;
}

body {
  background: var(--color-bg-primary);
  color: var(--color-text-body);
  font-family: var(--font-sans);
}
```

---

## If Using `tailwind.config.js` (Tailwind v3 / v3.4)

For projects on Tailwind v3, add this `theme.extend` block to `tailwind.config.js`. Copy-paste ready.

```json
{
  "theme": {
    "extend": {
      "colors": {
        "bg-primary":   "#020617",
        "bg-surface":   "#0F172A",
        "accent": {
          "500": "#38BDF8",
          "600": "#0EA5E9"
        },
        "text-heading": "#F8FAFC",
        "text-body":    "#94A3B8",
        "border-subtle": "rgba(255,255,255,0.08)"
      },
      "fontFamily": {
        "sans": ["'Inter'", "ui-sans-serif", "system-ui", "-apple-system", "sans-serif"],
        "mono": ["'Geist Mono'", "ui-monospace", "SFMono-Regular", "monospace"]
      },
      "borderRadius": {
        "card": "16px"
      },
      "boxShadow": {
        "glow-sm": "0 0 10px rgba(56,189,248,0.08)",
        "glow":    "0 0 20px rgba(56,189,248,0.10), 0 0 60px rgba(56,189,248,0.05)",
        "glow-lg": "0 0 30px rgba(56,189,248,0.15), 0 0 80px rgba(56,189,248,0.08)",
        "surface": "0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)"
      },
      "ringColor": {
        "accent": "#38BDF8"
      },
      "ringOffsetColor": {
        "primary": "#020617"
      }
    }
  }
}
```

---

## Custom Utility Classes

Add these to your CSS for reusable patterns that don't map cleanly to a single Tailwind utility.

```css
/* Glassmorphism surface */
.glass {
  background: rgba(15, 23, 42, 0.80);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

/* Ambient radial blob — position with absolute + inset utilities */
.blob-accent {
  background: radial-gradient(
    circle,
    rgba(56, 189, 248, 0.15) 0%,
    transparent 60%
  );
  pointer-events: none;
}

/* Subtle glow for interactive highlights */
.glow {
  box-shadow: 0 0 20px rgba(56,189,248,0.10), 0 0 60px rgba(56,189,248,0.05);
}

/* Reduced motion: disable transitions and blobs */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    transition-duration: 0s !important;
    animation-duration: 0s !important;
  }
  .blob-accent {
    display: none;
  }
}
```

---

## Safelist Recommendations

If using dynamic class names (e.g., status colors set by JS), safelist these patterns:

```js
safelist: [
  'bg-green-100', 'text-green-800',   // Value Score green
  'bg-yellow-100', 'text-yellow-800', // Value Score yellow
  'bg-zinc-100', 'text-zinc-600',     // Value Score gray
  'text-green-600',                    // Spread good
  'text-yellow-600',                   // Spread moderate
  'text-red-500',                      // Spread wide
]
```

---

## Sky-400 / Sky-500 Mapping

The design system accent colors map to Tailwind's sky palette:

| Design Token | Tailwind Built-in | Hex |
|---|---|---|
| `accent-500` | `sky-400` | `#38BDF8` |
| `accent-600` | `sky-500` | `#0EA5E9` |

If you prefer using Tailwind's built-in `sky-400` / `sky-500` classes instead of custom `accent-*` classes, that is acceptable — the hex values are identical. The custom tokens exist for semantic clarity.
