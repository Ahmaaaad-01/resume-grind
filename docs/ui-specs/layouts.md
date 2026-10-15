# Layouts — Prediction Markets

Grid systems, responsive rules, breakpoints, and page-level structure.

---

## Breakpoints

| Name | Min Width | Tailwind Prefix | Usage |
|---|---|---|---|
| Mobile | 0px | (default) | Single column, stacked layout |
| sm | 640px | `sm:` | Minor adjustments (padding, font bumps) |
| md | 768px | `md:` | Switch to multi-column grids |
| lg | 1024px | `lg:` | Full desktop layout |
| xl | 1280px | `xl:` | Max-width content container caps here |

---

## Page Container

All pages use a centered max-width container with horizontal padding.

```
Container: max-w-7xl mx-auto px-4 sm:px-6 lg:px-8
```

- `max-w-7xl` = 1280px — content never stretches wider than this.
- Horizontal padding scales from 16px (mobile) → 24px (sm) → 32px (lg).

---

## Event Viewer Layout (Main Page)

### Structure
```
┌─────────────────────────────────────────────┐
│  Header: Title + subtitle + ActionBar       │  py-10
├─────────────────────────────────────────────┤
│  Data Table (full width within container)   │
│  ┌─────┬─────┬────┬──────┬──────┬────────┐  │
│  │Event│ YES │ NO │ HL   │Spread│V.Score │  │
│  ├─────┼─────┼────┼──────┼──────┼────────┤  │
│  │ ... │     │    │      │      │        │  │
│  └─────┴─────┴────┴──────┴──────┴────────┘  │
└─────────────────────────────────────────────┘
```

### Responsive Behavior
- **Desktop (md+):** Full table with all 6 columns visible.
- **Mobile (<md):** Table scrolls horizontally (`overflow-x-auto`). Event column remains the widest. Consider hiding Spread column on narrow screens via `hidden md:table-cell`.

### Spacing
- Page vertical padding: `py-10` (40px).
- Gap between header and table: `space-y-6` (24px).
- Table container: `rounded-2xl border border-white/[0.08]`.

### Tailwind
```
Page:       min-h-screen bg-[#020617] px-6 py-10
Inner:      max-w-7xl mx-auto space-y-6
Header:     flex items-start justify-between
Table wrap: overflow-x-auto rounded-2xl border border-white/[0.08] bg-[#0F172A]
```

---

## General Spacing Rules

| Context | Recommended | Tailwind |
|---|---|---|
| Between page header and content | 24px | `space-y-6` |
| Inside a card | 16px–24px | `p-4` to `p-6` |
| Between card rows in a list | 1px divider | `divide-y divide-white/[0.08]` |
| Between a heading and its body text | 4px–8px | `mt-1` to `mt-2` |
| Between form fields | 16px | `space-y-4` |
| Page horizontal padding | 16px–32px | `px-4 sm:px-6 lg:px-8` |
