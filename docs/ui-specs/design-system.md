# Design System — Prediction Markets

## Aesthetic

High-end AI SaaS / FinTech. Minimalist, high-contrast, deep dark mode with glassmorphism surfaces and subtle neon glows. The interface should feel like a professional trading terminal — dense with information but visually calm.

---

## Color Palette

### Backgrounds

| Token Name | Hex | Tailwind Class | Usage |
|---|---|---|---|
| `--color-bg-primary` | `#020617` | `bg-primary` | Page-level background. Used on `<body>`, full-bleed sections, and hero areas. This is the deepest layer — true black/slate. |
| `--color-bg-surface` | `#0F172A` | `bg-surface` | Cards, modals, dropdowns, navigation bar, and any elevated container. One step lighter than primary to create depth. |

**Rule:** Primary BG (`#020617`) is the page canvas. Surface BG (`#0F172A`) is for any element that "floats" above the canvas — cards, nav, panels, tooltips. Never use Surface BG as a page background; never use Primary BG for a card.

### Accents

| Token Name | Hex | Tailwind Class | Usage |
|---|---|---|---|
| `--color-accent-500` | `#38BDF8` | `accent-primary` | Primary interactive color — buttons, links, focus rings, active states, Value Score highlights. Sky-400 equivalent. |
| `--color-accent-600` | `#0EA5E9` | `accent-secondary` | Hover states, secondary emphasis, pressed buttons, chart accents. Sky-500 equivalent. |

### Text

| Token Name | Hex | Tailwind Class | Usage |
|---|---|---|---|
| `--color-text-heading` | `#F8FAFC` | `text-heading` | H1, H2, H3, and any high-emphasis label. Slate-50. |
| `--color-text-body` | `#94A3B8` | `text-body` | Body copy, descriptions, secondary labels. Slate-400. |

### Borders

| Token Name | Value | Tailwind Class | Usage |
|---|---|---|---|
| `--color-border` | `rgba(255,255,255,0.08)` | `border-subtle` | Default border for cards, dividers, table rows, nav bottom edge. |

### Semantic Aliases

| Semantic Name | Maps To | Usage |
|---|---|---|
| `bg-primary` | `#020617` | Page background |
| `bg-surface` | `#0F172A` | Card/container background |
| `text-heading` | `#F8FAFC` | Headings and labels |
| `text-muted` | `#94A3B8` | Body text and descriptions |
| `accent-500` | `#38BDF8` | Primary accent |
| `accent-600` | `#0EA5E9` | Secondary accent / hover |
| `border-subtle` | `rgba(255,255,255,0.08)` | All borders |

---

## Typography

### Font Stack

- **Primary:** `'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif`
- **Monospace (data/tickers):** `'Geist Mono', ui-monospace, SFMono-Regular, monospace`

### Scale

| Element | Size | Weight | Letter Spacing | Line Height | Tailwind Example |
|---|---|---|---|---|---|
| H1 | 2.25rem (36px) | Bold (700) | -0.02em | 1.2 | `text-4xl font-bold tracking-tight` |
| H2 | 1.5rem (24px) | Semibold (600) | -0.02em | 1.3 | `text-2xl font-semibold tracking-tight` |
| H3 | 1.125rem (18px) | Semibold (600) | -0.02em | 1.4 | `text-lg font-semibold tracking-tight` |
| Body | 0.875rem (14px) | Regular (400) | normal | 1.625 | `text-sm font-normal leading-relaxed` |
| Small / Labels | 0.75rem (12px) | Medium (500) | 0.05em | 1.5 | `text-xs font-medium uppercase tracking-wide` |
| Utility / Tickers | 0.625rem (10px) | Regular (400) | 0.02em | 1.4 | `text-[10px] font-mono tracking-wide` |

### Rules

- Headings always use semibold or bold with `tracking-tight` (-0.02em). Never use regular weight for headings.
- Body text uses `leading-relaxed` for readability on dark backgrounds.
- Button labels and small utility text (category tags, column headers) use medium weight, uppercase, `tracking-wide`.

---

## Spacing Scale

| Token | Value (rem) | Value (px) | Tailwind | Usage |
|---|---|---|---|---|
| `--space-xs` | 0.25rem | 4px | `p-1` / `gap-1` | Inline icon spacing, tight gaps |
| `--space-sm` | 0.5rem | 8px | `p-2` / `gap-2` | Between related items (tag + text) |
| `--space-md` | 1rem | 16px | `p-4` / `gap-4` | Default padding inside cards and cells |
| `--space-lg` | 1.5rem | 24px | `p-6` / `gap-6` | Section padding, card-to-card gaps |
| `--space-xl` | 2.5rem | 40px | `p-10` / `gap-10` | Page-level vertical padding |
| `--space-2xl` | 5rem | 80px | `py-20` | Hero and feature section top/bottom |
| `--space-3xl` | 8rem | 128px | `py-32` | Maximum section padding for key pages |

---

## Border Radius

| Token | Value | Tailwind | Usage |
|---|---|---|---|
| `--radius-sm` | 6px | `rounded-md` | Badges, tags, small chips |
| `--radius-md` | 8px | `rounded-lg` | Buttons, inputs |
| `--radius-lg` | 16px | `rounded-2xl` | Cards, modals, containers (primary radius) |
| `--radius-full` | 9999px | `rounded-full` | Pills, avatar circles |

**Note:** The default card/container radius is **16px** (`rounded-2xl`). This is the signature radius for the product — use it consistently on all elevated surfaces.

---

## Effects

### Glassmorphism (Backdrop Blur)

- Apply `backdrop-blur-xl` (24px blur) on surfaces that overlay content (nav bar, modals, floating panels).
- Combine with a semi-transparent surface background: `bg-[#0F172A]/80`.
- Pair with `border border-white/[0.08]` for the frosted-glass edge.

### Radial Blobs

- Used as ambient background decoration behind hero areas and feature sections.
- Color: `#38BDF8` (accent primary) at ~15% opacity.
- Size: 400–600px diameter, positioned off-center using absolute positioning.
- CSS: `background: radial-gradient(circle at 30% 20%, rgba(56,189,248,0.15) 0%, transparent 60%)`.
- Never let blobs touch interactive elements or obscure text.

### Blue Glow (Outer Shadow)

- Used on primary buttons, accent cards, and featured/highlighted elements.
- CSS: `0 0 20px rgba(56,189,248,0.10), 0 0 60px rgba(56,189,248,0.05)`
- Tailwind: Use a custom `shadow-glow` utility (see `tailwind-suggested.md`).
- Keep glow subtle — 5–10% opacity maximum. It should be felt, not seen at a glance.

### Transitions

- All interactive state changes (hover, focus, active) use `transition duration-300 ease-in-out`.
- No animation on first paint. Motion is reserved for state changes only.
- Respect `prefers-reduced-motion` — disable transitions and blobs when active.
