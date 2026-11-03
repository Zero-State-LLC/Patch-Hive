# PatchHive · Cyber Hive design system

> Locked for Hallmark / product UI. Source of truth alongside `docs/brand/design-tokens.cyber-hive.json`.

## Genre

**atmospheric-technical** (Zero State cyber-hive) — dark graphite workbench, amber signal, cyan diagnostics. Not purple-SaaS, not cream-editorial.

## Typography

| Role | Stack |
|------|--------|
| Display / brand | `Space Grotesk, Inter, system-ui, sans-serif` → `var(--font-display)` |
| UI body | `Inter, Geist, system-ui, sans-serif` → `var(--font-ui)` |
| Mono / data | `JetBrains Mono, ui-monospace, monospace` → `var(--font-mono)` |

No italic headers. Brand name is hero-level on marketing folds.

## Color

| Token | Value | Use |
|-------|--------|-----|
| carbon / graphite / panel | `#08090B` / `#111318` / `#1A1D24` | Surfaces |
| border / titanium | `#2A2F3A` / `#8B919C` | Lines / muted |
| amber / cyan | `#F5A623` / `#3DDCFF` | Action / info |
| emerald / warn / danger | `#00C896` / `#FF8A3D` / `#E23D4A` | Status only |
| violet | `#7B61FF` | Diagnostics sparingly |

**Never rainbow** category accents. Light theme stays cool graphite-paper neutrals + amber action (not cream/bronze).

## Radius / elevation

- Card: `18px` (`--radius-md`)
- Control: `10px` (`--radius-sm`)
- Chips: squared (`--radius-sm`), not `999px` (progress bars may stay pill)
- Elevation: single soft shadow or border-only; no stacked theater

## Macrostructure families

| Surface | Allowed shapes |
|---------|----------------|
| Home / marketing | Brand-first full-bleed hero → one CTA group → optional single law list (no feature-card grids) |
| Auth | Split diptych: brand panel + form (no dual aurora orbs) |
| Workbench (racks, modules, cases, builder, registry) | Workspace header + dense lists/tables/catalogs |
| Admin | Workspace header + linked area list (no feature-card icon tiles) |

## Imagery

Prefer real brand assets under `/brand/` (`splash-hero.jpg`, lockups, hive-drone). Gradients are atmosphere only, not the main visual idea.

## Motion

Motion is signal: it carries a change of state, never decoration.

- A module entering a rail row slides into its slot. HP and power meters fill to their value. Results crossfade when filters change. The active nav item's amber rule draws in. A hovered row lights its faceplate edge.
- `transform` and `opacity` only. Durations: 120ms (press, tick), 220ms (hover, fill, crossfade), 420ms (a panel opening). Ease-out on arrival, no overshoot.
- No ambient loops, no glow-blur neon stacks. A loader is the only infinite animation.
- Honor `prefers-reduced-motion`: every animation shows its end state at once.

## Signature

**The rail.** Modules are drawn to scale in HP (1 HP = 5.08 mm) wherever they appear: as a faceplate in the catalog, as a slot in a rig row. A rig row is a 3U rail that fills toward its HP budget. Widths come from data; an unknown width is drawn as unknown, never guessed.

## Stamp

Major CSS entry: `frontend/src/index.css` carries `/* Hallmark · design-system: design.md · genre: atmospheric-technical · theme: cyber-hive */`.
