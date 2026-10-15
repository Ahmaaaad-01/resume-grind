# Examples & PR Review Rubric — Prediction Markets

Copy-only examples showing how to describe a page or block using the design spec, plus a rubric for reviewing visual/design PRs.

---

## Example Page Descriptions

### Event Viewer (Main Page)

> **Page background:** `bg-primary` (`#020617`), full viewport height.
>
> **Container:** `max-w-7xl mx-auto px-6 py-10`.
>
> **Header block:** Flex row, `items-start justify-between`. Left side: H2 heading ("Prediction Markets") in `text-heading` (`#F8FAFC`), `font-bold tracking-tight`. Subtitle below: `text-sm text-body` showing event count. Right side: ActionBar with two secondary pill buttons ("Sync from Kalshi", "Score Events").
>
> **Data table:** `rounded-2xl` container, `bg-surface` (`#0F172A`), `border border-white/[0.08]`. Header row: `bg-surface`, `text-xs uppercase tracking-wide text-body`. Six columns: Event, YES, NO, Headlines, Spread, Value Score. Body rows: `divide-y divide-white/[0.08]`, `hover:bg-white/[0.02]`. Value Score column: color-coded badge — green (>= 60), yellow (>= 35), gray (< 35).

### Navigation Bar

> **Position:** Fixed top, `z-50`, full width.
>
> **Background:** Glassmorphism — `bg-surface/80 backdrop-blur-xl`.
>
> **Bottom border:** `border-b border-white/[0.08]` — 1px subtle divider.
>
> **Height:** `h-16` (64px).
>
> **Content:** `max-w-7xl mx-auto px-6`, flex row centered vertically. Left: product name in `text-lg font-semibold text-heading`. Right: nav links in `text-sm text-body`, hover to `text-accent-500`.

---

## PR Review Rubric for Visual/Design Changes

Use this rubric when reviewing any PR that touches UI, styling, or layout.

### 1. Token Compliance
- [ ] Are all colors from `tokens.json`? No hardcoded hex values outside the token set.
- [ ] Are spacing values from the spacing scale (xs/sm/md/lg/xl)? No arbitrary pixel values.
- [ ] Is the correct border radius used? Cards = 16px (`rounded-2xl`), buttons = `rounded-full` or `rounded-lg`.

### 2. Color Usage
- [ ] Primary BG (`#020617`) used only for page-level backgrounds.
- [ ] Surface BG (`#0F172A`) used for cards, nav, elevated containers.
- [ ] Text heading color (`#F8FAFC`) used for headings and high-emphasis text only.
- [ ] Body text color (`#94A3B8`) used for descriptions and secondary content.
- [ ] Accent (`#38BDF8`) used only for interactive elements, links, and highlights — not for body text.

### 3. Typography
- [ ] Font family is Inter (or system fallback). No other fonts introduced.
- [ ] Headings use semibold/bold with `tracking-tight`.
- [ ] Body text uses regular weight with `leading-relaxed`.
- [ ] Utility/label text uses medium weight, uppercase, `tracking-wide`.

### 4. Effects
- [ ] Glassmorphism applied correctly: `backdrop-blur-xl` + semi-transparent surface BG + subtle border.
- [ ] Glow effects are subtle (5–10% opacity). Not overpowering.
- [ ] All transitions use `duration-300 ease-in-out`.
- [ ] No auto-playing animations.

### 5. Responsive
- [ ] Layout stacks to single column on mobile.
- [ ] Tables have `overflow-x-auto`.
- [ ] Padding adjusts at breakpoints (mobile is tighter).
- [ ] No horizontal scroll on mobile (outside of tables).

### 6. Accessibility
- [ ] Contrast ratios meet WCAG AA.
- [ ] Focus rings visible on all interactive elements (`focus-visible`).
- [ ] ARIA attributes present where needed (labels, roles, live regions).
- [ ] `prefers-reduced-motion` respected.

### 7. Consistency
- [ ] New components follow the patterns in `components-guidelines.md`.
- [ ] Spacing matches the page's existing rhythm.
- [ ] No new design patterns introduced without updating the spec.
