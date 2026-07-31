# 09 — Design System

Read this in full before writing any component. `src/design/` is the only place that
defines a colour, radius, duration, easing, or font. A hex code elsewhere is a bug.

---

## Direction: precision instrument, not trading terminal

The product's argument is **measurement over prediction**. The interface should therefore
look like laboratory instrumentation — anodised panels, engraved legends, phosphor
readouts, needles that settle rather than bounce — not like a Bloomberg pastiche.

This gives us a vocabulary nothing else in fintech uses, and every choice below derives
from it rather than from taste.

**Explicitly rejected** (these are the defaults, not choices):
- Warm cream + high-contrast serif + terracotta accent
- Near-black + single acid-green accent
- Broadsheet hairlines, zero radius, newspaper columns
- Glassmorphism, blurred blobs, purple→blue gradients, floating cards on gradient meshes

---

## Palette

Six values. Everything else is derived by opacity.

```css
/* Substrate — cool graphite, the instrument enclosure */
--ink:            #0D1114;   /* app background */
--panel:          #151B20;   /* panel face */
--panel-raised:   #1D252B;   /* elevated: modals, popovers, active rows */
--rule:           #2A343B;   /* hairlines, panel borders, table dividers */

/* The two accents encode a real distinction — see below */
--brass:          #E9B44C;   /* HUMAN / ACTIONABLE — brass, gold, the marigold register */
--phosphor:       #63C6C0;   /* MACHINE / MEASURED — instrument display cyan */

/* Direction — muted, not neon. These are data colours, never brand colours. */
--jade:           #5FA88A;   /* up */
--madder:         #C25450;   /* down */

/* Text */
--text-primary:   #E6EAEC;
--text-secondary: #96A3AB;
--text-tertiary:  #5E6D76;

/* Paper mode — engineering vellum, for reading long reports. NOT cream. */
--paper:          #E8E9E4;
--paper-panel:    #F1F2EE;
--paper-rule:     #C9CCC4;
--paper-ink:      #1A1F22;
```

### The accent rule — this is the important part

**Brass = things a human does or decides. Phosphor = things the machine measured.**

| Element | Colour |
|---|---|
| Primary buttons, active nav, user inputs, simulate action | `--brass` |
| Metric values, computed bands, coverage badges, `MEASURED`/`COMPUTED` labels | `--phosphor` |
| LLM narrative label (`INFERRED`) | `--brass` at 70% |
| Falsifier breach, invalidated thesis | `--madder` |

A user should be able to learn the system's epistemics from its colours alone.
This is structure encoding truth, which is the difference between a design and a skin.

### Direction colour rules
- `--jade` / `--madder` appear only on numbers, sparklines, and the P&L. Never on
  buttons, never on backgrounds, never on borders.
- Never use red/green as the *only* signal — pair with `▲ ▼` glyphs and sign.
- Colour-blind safe check: jade and madder differ in luminance by 12%, so they remain
  distinguishable in greyscale. Verify with a deuteranopia filter before shipping.

---

## Typography

Three faces, three jobs. All free.

```css
--font-display: 'Bricolage Grotesque Variable', sans-serif;  /* headings only */
--font-ui:      'General Sans Variable', sans-serif;          /* everything readable */
--font-data:    'Geist Mono Variable', ui-monospace;          /* every numeral, always */
```

- **Bricolage Grotesque** — variable width and optical-size axes. Used at 28px+ only,
  for page titles and the hero moment. Tight tracking (`-0.02em`), weight 700, `wdth` 96.
  Never in tables, never below 20px.
- **General Sans** (Fontshare) — UI, labels, prose. Weight 400/500/600.
- **Geist Mono** — **every number in the application, without exception**, with
  `font-variant-numeric: tabular-nums`. Digits must align in columns and must not
  reflow when animating. This is non-negotiable in a finance app.

### Scale

```css
--t-display:  clamp(1.75rem, 2.2vw, 2.5rem);   /* Bricolage 700 */
--t-title:    1.375rem;                         /* General Sans 600 */
--t-section:  1rem;                             /* General Sans 600 */
--t-body:     0.9375rem;                        /* General Sans 400, lh 1.6 */
--t-data-lg:  1.75rem;                          /* Geist Mono 500, tabular */
--t-data:     0.875rem;                         /* Geist Mono 400, tabular */
--t-label:    0.625rem;                         /* engraved legend, see below */
```

### The engraved legend — the structural signature

Every panel carries a small legend strip at its top-left:

```css
.legend {
  font-family: var(--font-ui);
  font-size: var(--t-label);       /* 10px */
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--phosphor);
  opacity: 0.75;
}
```

The legend's **text is always a provenance class**: `MEASURED`, `COMPUTED`, `INFERRED`,
`SOURCE`, `YOUR INPUT`. Not a decorative eyebrow. It carries information the reader needs
and it's how the report contract becomes visible.

This is the design's single most repeated element. It has to be right.

---

## Layout

```
┌──────┬───────────────────────────────────────────────────────┐
│      │  ▸ page title (Bricolage)          data as of · 30 Jul│
│ rail │───────────────────────────────────────────────────────│
│ 68px │  ┌─ MEASURED ─────────┐ ┌─ COMPUTED ────────────────┐ │
│      │  │                    │ │                           │ │
│ icons│  │  panel             │ │  panel                    │ │
│ only │  │                    │ │                           │ │
│      │  └────────────────────┘ └───────────────────────────┘ │
│      │  ┌─ INFERRED ──────────────────────────────────────┐  │
│      │  │                                                 │  │
│      │  └─────────────────────────────────────────────────┘  │
└──────┴───────────────────────────────────────────────────────┘
```

- Fixed 68px icon rail, no labels, tooltip on hover. Active item marked with a 2px
  brass bar on the left edge — a physical switch indicator, not a filled pill.
- Content max-width 1440px, 12-column grid, 20px gutter.
- Panels: `background: var(--panel)`, `border: 1px solid var(--rule)`,
  `border-radius: 3px`. Small radius — machined edges, not soft cards.
- **Panel depth without shadows:** a 1px inset top highlight at
  `rgba(255,255,255,0.04)` and a 1px bottom rule at `rgba(0,0,0,0.4)`.
  This reads as a bevelled metal face. Use box-shadow only on true overlays.
- Spacing scale: 4 / 8 / 12 / 20 / 32 / 52 (loosely Fibonacci; avoid the 8pt-grid look).

### Tables — the real workhorse
- Row height 38px, no zebra striping (it's dated and it fights the data colours).
- Divider: 1px `--rule` at 50% opacity.
- Row hover: `--panel-raised`, 90ms.
- Numeric columns right-aligned, `--font-data`, tabular.
- Sort indicator is a 1px underline on the header, not a caret.
- Sticky header with a 1px brass bottom rule.

---

## Motion

```css
--ease-settle: cubic-bezier(0.22, 1, 0.36, 1);   /* instrument settling */
--ease-quick:  cubic-bezier(0.4, 0, 0.2, 1);
--d-instant: 90ms;  --d-quick: 180ms;  --d-normal: 320ms;  --d-slow: 620ms;
```

**Rules:**
1. **Never bounce a number.** Money that overshoots and settles reads as unreliable.
   Number transitions use `--ease-settle`, no overshoot, tabular figures so width is fixed.
2. Panel entry: 8px rise + fade, `--d-normal`, staggered 40ms. Once, on route mount.
3. Chart lines draw via `stroke-dashoffset` over `--d-slow`, `--ease-quick`. Once.
4. Hover micro-interactions: `--d-instant`. Anything slower feels laggy on data-dense UI.
5. The calibration dial needle is the **only** element permitted a settling oscillation
   (one small overshoot, critically damped) — because that's what a real needle does,
   and it's the signature.
6. No parallax. No scroll-jacking. No ambient background animation. This is a tool.

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 1ms !important;
    transition-duration: 1ms !important;
  }
}
```
The 3D views fall back to static orthographic renders.

---

## The signature: the Calibration Dial

Dashboard hero. Not a KPI card. This is the thing the app is remembered for.

**Concept.** A machined instrument face, ~360px, showing three needles — SHORT, MID, LONG —
each pointing at that horizon's measured direction hit rate on an arc from 30% to 80%.
A `50%` coin-flip mark is engraved on the face. Everything below 50% sits in a subtly
darker sector of the dial. The instrument measures the instrument.

**Build:** SVG for the face and needles (crisp, accessible, scalable), CSS/WebGL only for
the bezel specular. Do not build this in three.js — vector is sharper here and the depth
is achieved with layered gradients.

```
Layers, back to front:
1. Bezel ring       radial-gradient, brushed-metal noise via feTurbulence, 3px
2. Face             --panel, subtle inner shadow from bezel
3. Sub-50% sector   --ink at 40%, arc fill
4. Tick marks       major every 10% (2px, --text-tertiary), minor every 2% (1px, 30%)
5. Engraved numerals--font-data 10px, --text-tertiary, along the arc
6. Coin-flip mark   1px --madder radial line at 50%, labelled "COIN FLIP"
7. Needles ×3       --phosphor (calibrated) or --text-tertiary (uncalibrated),
                    2px tapered, with a 4px counterweight tail
8. Hub              --brass, 12px, with a 1px dark rim
9. Legend           "CALIBRATION · n=143 SCORED CALLS" below the face
```

**Behaviour:**
- On mount, needles sweep from rest to value over 900ms with one small overshoot.
- A horizon with < 20 scored calls rests at a detent below the arc, marked
  `UNCALIBRATED`, rendered in `--text-tertiary`, and does not animate.
- Hovering a needle raises a small readout: hit rate, n, net alpha, Brier.
- Beneath the dial, one line of plain deterministic verdict text per horizon.

**Accessibility:** the dial has `role="img"` with a full text alternative, and an
identical data table is rendered directly beneath it — not hidden, not behind a toggle.

---

## The second 3D moment: allocation scatter

The only other three.js surface. Risk × return × liquidity, orthographic camera, orbit
only. Full spec in `docs/04-ALLOCATION-ENGINE.md`. Everything else in the app is flat.

Two 3D moments in the entire application. That restraint is what makes them land.

---

## Component inventory

Build these in `src/design/primitives/` before any feature work:

```
Panel            legend prop (required), title, actions, coverage badge
Legend           the engraved provenance strip
Metric           label + value + unit + delta + provenance dot; tabular, never wraps
DataTable        sortable, sticky header, virtualised beyond 100 rows
Band             bear/base/bull horizontal range with base marker and n= readout
Sparkline        56×18, single stroke, no axes, no fill
Needle           shared by the dial and any gauge
Verdict          plain-text system judgement, three severities
Falsifier        condition + current value + distance to breach + status pip
Gate             blocked/passed with the reason printed, used all over the planner
CostBreakdown    waterfall from gross to net, always expandable
Stale            "as of" chip; turns madder past threshold
Empty            never "no data" — always names what's missing and what would fix it
```

`Metric` and `Panel` account for ~70% of the UI. Get them exactly right first;
build one screen with them; screenshot; critique; then continue.

---

## Copy rules

- Sentence case everywhere except engraved legends (uppercase, tracked).
- No exclamation marks. No emoji. No encouragement.
- Errors state what happened and what to do: *"Fundamentals for RELIANCE are 118 days old.
  Long-horizon scoring needs data under 100 days. Re-run ingestion or pin a manual override."*
- Empty states are instructions, not apologies: *"No short-horizon candidates cleared the
  cost hurdle today. That's the expected outcome most days."*
- Never call anything "AI-powered", "smart", or "intelligent". The word is `inferred`.

---

## Quality floor (not optional)

- Responsive to 390px. The rail collapses to a bottom bar; tables become stacked
  `Metric` cards; the dial scales to 280px.
- Visible keyboard focus: 2px `--brass` outline, 2px offset. Never `outline: none`.
- Every interactive element reachable by tab, in visual order.
- Contrast: all text ≥ 4.5:1 against its panel. Check `--text-tertiary` on `--panel`
  specifically — it will fail at small sizes, so raise it rather than shipping it.
- Charts have text alternatives.
- Test both themes and both motion preferences before calling a screen done.

## Before you call any screen finished

Screenshot it with Playwright. Look at it. Ask: could this be any other fintech app?
If yes, the legend strip, the brass/phosphor split, or the type scale isn't doing its job.
Then remove one thing.
