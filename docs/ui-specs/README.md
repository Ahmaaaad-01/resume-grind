# UI Specifications — Prediction Markets

## Purpose

This folder is the single source of truth for the visual design system behind **Prediction Markets**. It contains color tokens, typography rules, layout guidance, component specs, and accessibility requirements — everything a developer or designer needs to implement or review UI changes without guessing.

No React or component code lives here. Only design documentation, token definitions, and implementation guidance.

## How to Use These Specs

| Role | Start here |
|---|---|
| **Frontend developer** | `design-system.md` for visual rules → `tokens.json` for exact values → `tailwind-suggested.md` for config snippets |
| **Designer** | `design-system.md` for the system overview → `components-guidelines.md` for component specs → `layouts.md` for page structure |
| **PR reviewer** | `examples.md` for the review rubric → `accessibility.md` for the a11y checklist |

## Updating Tokens

1. Edit `tokens.json` with the new or changed values.
2. Mirror the change in `design-system.md` (verbal description) and `tailwind-suggested.md` (Tailwind config).
3. Add an entry to `CHANGELOG.md` with the date, author, summary, and files changed.
4. Open a PR — reviewers should verify the token change against the accessibility checklist in `accessibility.md`.

## Versioning

Tokens follow semantic versioning recorded in `CHANGELOG.md`. Any breaking change to an existing token name or value bumps the minor version. Additive tokens (new colors, new spacing steps) are patch-level.

## File Index

| File | Contents |
|---|---|
| `design-system.md` | Full verbal design system — colors, typography, spacing, effects |
| `tokens.json` | Canonical design tokens in JSON |
| `tailwind-suggested.md` | Tailwind `theme.extend` snippets, copy-paste ready |
| `components-guidelines.md` | High-level specs for every primary UI piece |
| `layouts.md` | Grid, responsive, and page-level layout rules |
| `accessibility.md` | A11y checklist, contrast ratios, ARIA guidance |
| `examples.md` | Copy-only page descriptions and PR review rubric |
| `CHANGELOG.md` | Version history template |
