# Accessibility Checklist — Prediction Markets

---

## Color Contrast

| Pairing | Foreground | Background | Contrast Ratio | WCAG AA (4.5:1) | WCAG AAA (7:1) |
|---|---|---|---|---|---|
| Heading on Primary BG | `#F8FAFC` | `#020617` | **19.6:1** | Pass | Pass |
| Heading on Surface BG | `#F8FAFC` | `#0F172A` | **14.4:1** | Pass | Pass |
| Body text on Primary BG | `#94A3B8` | `#020617` | **7.6:1** | Pass | Pass |
| Body text on Surface BG | `#94A3B8` | `#0F172A` | **5.6:1** | Pass | Fail |
| Accent on Primary BG | `#38BDF8` | `#020617` | **10.1:1** | Pass | Pass |
| Accent on Surface BG | `#38BDF8` | `#0F172A` | **7.4:1** | Pass | Pass |
| Black text on Accent button | `#000000` | `#38BDF8` | **10.7:1** | Pass | Pass |

### Rules
- All text must meet WCAG AA (4.5:1 for normal text, 3:1 for large text).
- Headings on both backgrounds pass AAA. Body text on Surface BG passes AA but not AAA — acceptable for secondary information.
- Never place body-color text (`#94A3B8`) on a lighter background than Surface BG.
- Color must not be the sole indicator of state. Always pair color with text labels, icons, or patterns.

---

## Keyboard Navigation

### Tab Order
- All interactive elements (links, buttons, inputs, table sort headers) must be reachable via Tab key.
- Tab order must follow visual reading order (top-to-bottom, left-to-right).
- No keyboard traps — Tab must always advance; Escape must always close modals/dropdowns.

### Focus Management
- Modals: focus moves to the modal on open, returns to the trigger on close.
- Dropdowns: focus moves to the first item on open; arrow keys navigate within.
- After an action (Sync, Score), keep focus on the button that triggered it.

### Skip Link
- Include a "Skip to main content" link as the first focusable element on every page.
- Visually hidden until focused: `sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4`.

---

## Focus States

### Visible Focus Ring
Every interactive element must have a clearly visible focus indicator when navigated to via keyboard.

**Standard focus ring (use on all interactive elements):**
```
focus-visible:outline-none
focus-visible:ring-2
focus-visible:ring-[#38BDF8]
focus-visible:ring-offset-2
focus-visible:ring-offset-[#020617]
```

- Ring color: Accent primary (`#38BDF8`) — high contrast against both Primary and Surface BGs.
- Ring offset: 2px, colored to match the underlying background (`#020617` for page-level, `#0F172A` for elements on cards).
- Use `focus-visible` (not `focus`) to avoid showing rings on mouse clicks.

### Focus on Dark Surfaces
For elements inside cards (Surface BG), adjust the ring offset color:
```
focus-visible:ring-offset-[#0F172A]
```

---

## ARIA Guidance

### Navigation
```html
<nav aria-label="Main navigation">
  <a href="/" aria-current="page">Dashboard</a>
  <a href="/tracker">Bet Tracker</a>
</nav>
```

### Buttons
```html
<!-- Text button — no extra ARIA needed -->
<button type="button">Sync from Kalshi</button>

<!-- Icon-only button — requires aria-label -->
<button type="button" aria-label="Refresh data">
  <!-- SVG icon -->
</button>

<!-- Loading state -->
<button type="button" aria-busy="true" disabled>
  Scoring...
</button>
```

### Data Table
```html
<table aria-label="Prediction market events ranked by Value Score">
  <thead>
    <tr>
      <th scope="col">Event</th>
      <th scope="col" aria-sort="descending">Value Score</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Who will the next Pope be? — Pietro Parolin</td>
      <td>85</td>
    </tr>
  </tbody>
</table>
```

### Status Messages
After Sync or Score actions complete, announce the result to screen readers:
```html
<div role="status" aria-live="polite" class="sr-only">
  Scored 20 events successfully.
</div>
```

### Badges / Chips
```html
<!-- Value Score badge — include sr-only context -->
<span class="bg-green-100 text-green-800 rounded px-2 py-0.5 text-xs font-semibold">
  85
  <span class="sr-only">out of 100 — high value</span>
</span>
```

---

## Motion & Reduced Motion

### Default Motion
- Transitions: `duration-300 ease-in-out` on interactive state changes (hover, focus, active).
- No auto-playing animations, carousels, or infinite loops.
- Radial blobs are static (CSS gradients, not animated).

### `prefers-reduced-motion: reduce`
When the user has reduced motion enabled:
- Disable all `transition-duration` and `animation-duration` (set to `0s`).
- Hide decorative blobs entirely.
- Keep focus rings and state changes instant (not removed — just instant).

```css
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

## Accessible Button Markup Examples

### Primary Button (Full Accessibility)
```html
<button
  type="button"
  class="inline-flex items-center justify-center rounded-full bg-[#38BDF8] text-black font-medium px-6 py-3 transition duration-300 hover:bg-[#0EA5E9] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#38BDF8] focus-visible:ring-offset-2 focus-visible:ring-offset-[#020617]"
>
  Score Events
</button>
```

### Icon Button (Accessible)
```html
<button
  type="button"
  aria-label="Sync events from Kalshi"
  class="inline-flex items-center justify-center rounded-full border border-white/[0.08] text-[#94A3B8] p-3 transition duration-300 hover:text-[#F8FAFC] hover:border-white/[0.15] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#38BDF8] focus-visible:ring-offset-2 focus-visible:ring-offset-[#020617]"
>
  <!-- SVG icon here -->
</button>
```

### Disabled Button
```html
<button
  type="button"
  disabled
  aria-disabled="true"
  class="inline-flex items-center justify-center rounded-full bg-[#38BDF8] text-black font-medium px-6 py-3 opacity-50 cursor-not-allowed"
>
  Score Events
</button>
```

---

## Checklist Summary

- [ ] All text meets WCAG AA contrast (4.5:1 normal, 3:1 large)
- [ ] Color is never the sole state indicator
- [ ] All interactive elements are keyboard reachable via Tab
- [ ] Visible focus ring on every interactive element (using `focus-visible`)
- [ ] No keyboard traps
- [ ] Skip-to-content link present
- [ ] `<nav>` has `aria-label`
- [ ] Data tables use `<th scope="col">` and `aria-sort` for sorted columns
- [ ] Icon-only buttons have `aria-label`
- [ ] Loading/disabled states use `aria-busy` / `aria-disabled`
- [ ] Action results announced via `role="status" aria-live="polite"`
- [ ] `prefers-reduced-motion` disables transitions and hides decorative blobs
- [ ] Form inputs have associated labels and error states use `aria-describedby`
