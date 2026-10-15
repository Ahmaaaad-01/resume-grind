# Component Guidelines — Prediction Markets

High-level visual specifications for every primary UI piece. No component code — only purpose, visual specs, Tailwind mappings, and accessibility notes.

---

## Navigation Bar

### Purpose
Fixed top navigation. Always visible. Contains the product name, primary nav links, and action buttons (Sync, Score).

### Visual Specs
- **Position:** Fixed top, full width, z-50.
- **Background:** Surface BG at 80% opacity with backdrop blur — glassmorphism.
- **Height:** 64px (h-16).
- **Bottom border:** 1px solid `rgba(255,255,255,0.08)`.
- **Inner padding:** `px-6` horizontal, content centered with `max-w-7xl mx-auto`.
- **Logo/product name:** Text heading color (`#F8FAFC`), font-semibold, text-lg.
- **Nav links:** Text body color (`#94A3B8`), hover transitions to accent (`#38BDF8`).

### Tailwind Mapping
```
Nav container: fixed top-0 inset-x-0 z-50 h-16 bg-[#0F172A]/80 backdrop-blur-xl border-b border-white/[0.08]
Nav inner:     max-w-7xl mx-auto px-6 flex items-center justify-between h-full
Product name:  text-lg font-semibold text-[#F8FAFC] tracking-tight
Nav link:      text-sm text-[#94A3B8] hover:text-[#38BDF8] transition duration-300
```

### Accessibility
- Use `<nav>` element with `aria-label="Main navigation"`.
- Links must be focusable with visible focus ring: `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#38BDF8] focus-visible:ring-offset-2 focus-visible:ring-offset-[#020617]`.
- Current page link should have `aria-current="page"`.

---

## Buttons

### Purpose
Primary and secondary actions — syncing data, scoring events, navigation, and confirmations.

### Variants

#### Primary Button
- **Background:** Accent primary `#38BDF8`.
- **Text:** Black (`#000000`), font-medium.
- **Shape:** Pill (rounded-full), px-6 py-3.
- **Hover:** Background shifts to accent secondary `#0EA5E9`, subtle glow appears.
- **Active/Pressed:** Scale down slightly (`active:scale-[0.98]`).
- **Focus:** 2px ring in accent color with offset matching page BG.

#### Secondary Button
- **Background:** Transparent.
- **Border:** 1px solid `rgba(255,255,255,0.08)`.
- **Text:** Text body color `#94A3B8`, hover shifts to `#F8FAFC`.
- **Shape:** Pill (rounded-full), px-6 py-3.
- **Hover:** Border brightens to `rgba(255,255,255,0.15)`, background `rgba(255,255,255,0.03)`.

### Tailwind Mapping
```
Primary:   inline-flex items-center justify-center rounded-full bg-[#38BDF8] text-black font-medium px-6 py-3 transition duration-300 hover:bg-[#0EA5E9] hover:shadow-[0_0_20px_rgba(56,189,248,0.10)] active:scale-[0.98]
Secondary: inline-flex items-center justify-center rounded-full border border-white/[0.08] text-[#94A3B8] font-medium px-6 py-3 transition duration-300 hover:border-white/[0.15] hover:bg-white/[0.03] hover:text-[#F8FAFC]
Disabled:  opacity-50 cursor-not-allowed pointer-events-none
```

### Accessibility
- Use `<button>` elements (not `<div>` or `<a>` for actions).
- Include descriptive text or `aria-label` if button contains only an icon.
- Focus state: `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#38BDF8] focus-visible:ring-offset-2 focus-visible:ring-offset-[#020617]`.
- Disabled buttons must have `disabled` attribute and `aria-disabled="true"`.
- Loading state: swap label to "Loading..." or add `aria-busy="true"` with a spinner.

---

## Cards & Containers

### Purpose
Primary content wrapper — event rows, data panels, stat boxes, and analysis panels.

### Visual Specs
- **Border radius:** 16px (`rounded-2xl`) — the signature radius.
- **Background:** Gradient from `#0F172A` to a slightly darker tone, or solid `#0F172A`.
- **Border:** 1px solid `rgba(255,255,255,0.08)`.
- **Padding:** `p-4` for compact cards, `p-6` for standard cards.
- **Shadow:** `shadow-surface` for depth (`0 1px 3px rgba(0,0,0,0.4)`).
- **Hover (if interactive):** Border brightens, subtle glow appears.

### Tailwind Mapping
```
Standard card:     rounded-2xl bg-[#0F172A] border border-white/[0.08] p-6 shadow-[0_1px_3px_rgba(0,0,0,0.4)]
Interactive card:  rounded-2xl bg-[#0F172A] border border-white/[0.08] p-6 transition duration-300 hover:border-white/[0.12] hover:shadow-[0_0_20px_rgba(56,189,248,0.10)]
Gradient card:     rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-white/[0.08] p-6
Featured card:     rounded-2xl bg-[#0F172A] border border-[#38BDF8]/30 p-6 shadow-[0_0_20px_rgba(56,189,248,0.10)]
```

### Accessibility
- Interactive cards should use `role="button"` or be wrapped in an `<a>` if they navigate.
- If clickable, ensure the entire card area is the click target (not just the text).
- Provide a visible focus ring on interactive cards.

---

## Data Table

### Purpose
The primary event viewer — displays events ranked by Value Score with market data.

### Visual Specs
- **Container:** `rounded-2xl` border, white/8% border, surface BG.
- **Header row:** Surface BG slightly lighter (`bg-[#0F172A]`), uppercase `text-xs tracking-wide` in text-body color.
- **Body rows:** Divided by 1px `border-white/[0.08]`, hover highlights to `bg-white/[0.02]`.
- **Cell padding:** `px-4 py-3`.
- **Numeric columns** (YES, NO, Spread): Right-aligned or center-aligned, monospace optional.
- **Value Score badge:** Colored chip — green (`bg-green-100 text-green-800` for score >= 60), yellow (>= 35), gray (< 35).

### Tailwind Mapping
```
Table wrapper:  overflow-x-auto rounded-2xl border border-white/[0.08] bg-[#0F172A]
Table:          w-full text-sm
Header row:     border-b border-white/[0.08] bg-[#0F172A] text-[#94A3B8] text-xs uppercase tracking-wide
Header cell:    px-4 py-3
Body row:       hover:bg-white/[0.02] transition-colors
Body cell:      px-4 py-3
```

### Accessibility
- Use semantic `<table>`, `<thead>`, `<tbody>`, `<th scope="col">`.
- Sortable columns should have `aria-sort="ascending"` or `"descending"`.
- Ensure table is scrollable on mobile with `overflow-x-auto` and a focusable scroll container.

---

## Inputs & Forms

### Purpose
Search fields, text inputs, selects — used for filtering events or entering bet data.

### Visual Specs
- **Background:** `#0F172A` (surface).
- **Border:** 1px solid `rgba(255,255,255,0.08)`, radius `rounded-lg` (8px).
- **Text:** `#F8FAFC` for input value, `#94A3B8` for placeholder.
- **Focus:** Border transitions to `#38BDF8`, ring appears (2px accent ring).
- **Disabled:** `opacity-50`, no pointer events, background darkens slightly.
- **Padding:** `px-4 py-2.5`.

### Tailwind Mapping
```
Input:    w-full rounded-lg bg-[#0F172A] border border-white/[0.08] px-4 py-2.5 text-sm text-[#F8FAFC] placeholder:text-[#94A3B8] transition duration-300 focus:border-[#38BDF8] focus:ring-2 focus:ring-[#38BDF8]/30 focus:outline-none
Disabled: opacity-50 cursor-not-allowed
```

### Accessibility
- Every input must have an associated `<label>` (visible or `sr-only`).
- Error states: red border + `aria-invalid="true"` + error message linked via `aria-describedby`.
- Required fields: `aria-required="true"` plus visible indicator.

