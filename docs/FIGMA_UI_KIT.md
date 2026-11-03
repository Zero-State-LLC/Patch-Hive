# PatchHive Figma UI Kit

## Overview

Complete design system and component library for building PatchHive interfaces. This UI kit provides all visual elements, components, and patterns needed to maintain brand consistency across the platform.

---

## **⬡ DESIGN TOKENS**

### **Color Palette**

```
PRIMARY COLORS:
├── Cyan Hex:      #7FF7FF  (Primary accent, links, highlights)
├── Deep Black:    #020407  (Primary background)
├── Magenta Glow:  #FF1EA0  (Secondary accent, warnings, CTAs)
└── Signal Green:  #00FF88  (Success states, active indicators)

GRAYSCALE:
├── Near Black:    #0A0E14  (Secondary background)
├── Dark Gray:     #1C2128  (Card backgrounds, panels)
├── Mid Gray:      #3D4450  (Borders, dividers)
├── Light Gray:    #8B92A0  (Secondary text, disabled states)
└── Off White:     #E8ECF0  (Body text on dark backgrounds)

SEMANTIC COLORS:
├── Success:       #00FF88
├── Warning:       #FFB800
├── Error:         #FF1EA0
└── Info:          #7FF7FF

OPACITY VARIANTS:
├── 10%: rgba(127, 247, 255, 0.1) — Subtle backgrounds
├── 20%: rgba(127, 247, 255, 0.2) — Hover states
├── 40%: rgba(127, 247, 255, 0.4) — Disabled elements
├── 60%: rgba(127, 247, 255, 0.6) — Secondary UI
└── 100%: rgba(127, 247, 255, 1.0) — Primary UI
```

### **Typography**

```
FONT FAMILIES:
├── Monospace: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace
└── Fallback:  system-ui, -apple-system, sans-serif

TYPE SCALE:
├── Display:    48px / 700 / 1.1 / 0.05em
├── H1:         32px / 700 / 1.2 / 0.05em
├── H2:         24px / 600 / 1.3 / 0.05em
├── H3:         20px / 600 / 1.4 / 0.05em
├── H4:         18px / 600 / 1.4 / 0.03em
├── Body:       14px / 400 / 1.6 / normal
├── Body Small: 12px / 400 / 1.5 / normal
└── Caption:    10px / 400 / 1.4 / 0.05em

TEXT STYLES:
├── All Caps: text-transform: uppercase; letter-spacing: 0.1em
├── Code:     font-family: monospace; background: rgba(127, 247, 255, 0.1)
└── Link:     color: #7FF7FF; text-decoration: none; hover: underline
```

### **Spacing System**

```
BASE UNIT: 4px

SCALE:
├── xs:   4px   (0.25rem)
├── sm:   8px   (0.5rem)
├── md:   16px  (1rem)
├── lg:   24px  (1.5rem)
├── xl:   32px  (2rem)
├── 2xl:  48px  (3rem)
├── 3xl:  64px  (4rem)
└── 4xl:  96px  (6rem)

COMPONENT PADDING:
├── Button:       12px 24px
├── Input:        12px 16px
├── Card:         24px
├── Modal:        32px
└── Page Section: 48px
```

### **Border Radius**

```
├── None:   0px
├── Small:  2px  (Buttons, inputs)
├── Medium: 4px  (Cards, panels)
├── Large:  8px  (Modals, containers)
└── Full:   9999px (Pills, avatars)
```

### **Shadows & Effects**

```
BOX SHADOWS:
├── sm:  0 1px 2px rgba(127, 247, 255, 0.1)
├── md:  0 4px 8px rgba(127, 247, 255, 0.15)
├── lg:  0 8px 16px rgba(127, 247, 255, 0.2)
└── xl:  0 16px 32px rgba(127, 247, 255, 0.25)

GLOWS:
├── Cyan Glow:    0 0 20px rgba(127, 247, 255, 0.5)
├── Magenta Glow: 0 0 20px rgba(255, 30, 160, 0.5)
└── Intense Glow: 0 0 40px rgba(127, 247, 255, 0.8)

FILTERS:
├── Blur:     filter: blur(4px)
├── Brighten: filter: brightness(1.2)
└── Desaturate: filter: saturate(0.5)
```

---

## **⬡ COMPONENT LIBRARY**

### **Buttons**

```
VARIANTS:
├── Primary:   bg: #7FF7FF, color: #020407, hover: glow
├── Secondary: bg: transparent, border: #7FF7FF, color: #7FF7FF
├── Danger:    bg: #FF1EA0, color: #020407
├── Ghost:     bg: transparent, color: #7FF7FF, hover: bg-10%
└── Disabled:  bg: #3D4450, color: #8B92A0, opacity: 0.5

SIZES:
├── Small:  font: 12px, padding: 8px 16px, height: 32px
├── Medium: font: 14px, padding: 12px 24px, height: 40px
└── Large:  font: 16px, padding: 16px 32px, height: 48px

STATES:
├── Default
├── Hover:    transform: translateY(-2px), glow
├── Active:   transform: translateY(0), glow-intense
├── Disabled: opacity: 0.5, cursor: not-allowed
└── Loading:  spinner animation
```

### **Inputs**

```
TEXT INPUT:
├── Border: 2px solid rgba(127, 247, 255, 0.3)
├── Focus:  border: #7FF7FF, glow
├── Error:  border: #FF1EA0, error message below
└── Disabled: opacity: 0.5, cursor: not-allowed

SELECT DROPDOWN:
├── Similar to text input
├── Arrow indicator (chevron down)
└── Dropdown menu with hover states

CHECKBOX / RADIO:
├── Size: 20px × 20px
├── Border: 2px solid #7FF7FF
├── Checked: filled with #7FF7FF, checkmark/dot
└── Hover: glow effect

TOGGLE SWITCH:
├── Width: 44px, Height: 24px
├── Track: bg: #3D4450 (off), #7FF7FF (on)
└── Thumb: 20px circle, slides on toggle
```

### **Cards**

```
BASE CARD:
├── Background: #1C2128
├── Border: 1px solid rgba(127, 247, 255, 0.2)
├── Padding: 24px
├── Border Radius: 4px
└── Hover: border: #7FF7FF, subtle glow

MODULE CARD:
├── Hex icon at top
├── Title (module name)
├── HP width badge
├── I/O ports list
└── Power draw indicator

PATCH CARD:
├── Waveform thumbnail
├── Patch name + category
├── Upvote/downvote controls
├── Comment count
└── Seed display
```

### **Navigation**

```
TOP NAV:
├── Height: 64px
├── Background: #0A0E14
├── Border Bottom: 1px solid rgba(127, 247, 255, 0.2)
├── Logo on left
├── Nav links center
└── User menu right

SIDEBAR:
├── Width: 240px
├── Background: #0A0E14
├── Nav items with icons
├── Hover: bg: rgba(127, 247, 255, 0.1)
└── Active: bg: rgba(127, 247, 255, 0.2), border-left: 3px solid #7FF7FF

BREADCRUMBS:
├── Color: #8B92A0
├── Separator: / or ⬡
└── Current: color: #7FF7FF
```

### **Modals & Overlays**

```
MODAL:
├── Background: #1C2128
├── Border: 2px solid #7FF7FF
├── Padding: 32px
├── Max Width: 600px
├── Border Radius: 8px
└── Backdrop: rgba(2, 4, 7, 0.8), blur(4px)

TOOLTIP:
├── Background: #0A0E14
├── Border: 1px solid #7FF7FF
├── Padding: 8px 12px
├── Font Size: 12px
└── Arrow pointer

DROPDOWN MENU:
├── Background: #1C2128
├── Border: 1px solid rgba(127, 247, 255, 0.3)
├── Item Hover: bg: rgba(127, 247, 255, 0.1)
└── Divider: 1px solid rgba(127, 247, 255, 0.2)
```

### **Badges & Tags**

```
BADGE:
├── Small: 20px height, 8px padding
├── Background: rgba(127, 247, 255, 0.2)
├── Color: #7FF7FF
├── Border Radius: 2px
└── Font: 10px, uppercase, bold

TAG (interactive):
├── Similar to badge
├── Hover: bg: rgba(127, 247, 255, 0.3)
├── X close button on right
└── Transition: all 0.2s
```

### **Icons**

```
MODULE TYPE ICONS (see docs/assets/icons/module-types.svg):
├── VCO:   Sine wave in hex
├── VCF:   Filter slope in hex
├── VCA:   Amplitude envelope in hex
├── ENV:   ADSR curve in hex
├── LFO:   Low freq wave in hex
├── SEQ:   Step sequence in hex
├── MIX:   Crossfader in hex
├── FX:    Echo/delay in hex
├── UTIL:  Mult/switch in hex
└── NOISE: Random in hex

UI ICONS:
├── Size: 16px, 20px, 24px variants
├── Stroke Width: 2px
├── Color: #7FF7FF (inherit from parent)
└── Hover: glow effect

ICON BUTTON:
├── Size: 32px × 32px (medium)
├── Background: transparent
├── Hover: bg: rgba(127, 247, 255, 0.1)
└── Icon centered
```

### **Loading States**

```
SKELETON (no spinners; see frontend/src/components/Skeletons.tsx):
├── Shaped like what is coming: list rows, a rail of faceplates, the signal chain, a readout figure
├── Fill: --color-muted mixed 18% into --color-paper-2, so it reads in both themes
├── Animation: opacity pulse, --dur-loader alternating (the only infinite animation)
└── Border Radius: --radius-plate

PROGRESS BAR:
├── Height: 4px
├── Background: #3D4450
├── Fill: linear-gradient(90deg, #7FF7FF, #FF1EA0)
└── Indeterminate: animated slide
```

### **Tables**

```
DATA TABLE:
├── Header: bg: #1C2128, border-bottom: 2px solid #7FF7FF
├── Row: border-bottom: 1px solid rgba(127, 247, 255, 0.1)
├── Row Hover: bg: rgba(127, 247, 255, 0.05)
├── Cell Padding: 12px 16px
└── Sortable: header with arrow indicators
```

---

## **⬡ LAYOUT PATTERNS**

### **Grid System**

```
CONTAINER:
├── Max Width: 1200px
├── Padding: 24px (mobile), 48px (desktop)
└── Margin: 0 auto

GRID:
├── Columns: 12
├── Gutter: 24px
└── Breakpoints:
    ├── xs: 0px
    ├── sm: 640px
    ├── md: 768px
    ├── lg: 1024px
    └── xl: 1280px
```

### **Page Layouts**

```
FULL WIDTH:
├── No max-width constraint
└── Used for: Home, Gallery, Feeds

CENTERED CONTENT:
├── Max Width: 800px
├── Centered with auto margins
└── Used for: Articles, Forms, Single Patch View

SIDEBAR LAYOUT:
├── Sidebar: 240px (fixed)
├── Main: flex: 1
└── Used for: App Dashboard, Settings

TWO COLUMN:
├── Left: 60% (content)
├── Right: 40% (sidebar/meta)
└── Used for: Patch Details, Module Info
```

---

## **⬡ ANIMATION PRINCIPLES**

### **Timing Functions**

```
├── Ease Out:     cubic-bezier(0.0, 0.0, 0.2, 1)    [UI interactions]
├── Ease In Out:  cubic-bezier(0.4, 0.0, 0.2, 1)    [Smooth transitions]
├── Spring:       cubic-bezier(0.34, 1.56, 0.64, 1) [Bouncy effects]
└── Linear:       linear                             [Constant motion]
```

### **Durations**

```
├── Instant:  0ms       [Immediate feedback]
├── Fast:     150ms     [Micro-interactions]
├── Normal:   300ms     [Standard transitions]
├── Slow:     500ms     [Complex animations]
└── Reveal:   800ms     [Page transitions]
```

### **Keyframe Patterns**

```
PULSE:
@keyframes pulse {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.05); }
}

GLOW:
@keyframes glow {
  0%, 100% { filter: drop-shadow(0 0 5px #7FF7FF); }
  50% { filter: drop-shadow(0 0 20px #7FF7FF); }
}

SLIDE-IN:
@keyframes slideIn {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

ROTATE:
@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

---

## **⬡ ACCESSIBILITY**

### **Focus States**

```
├── Outline: 2px solid #7FF7FF
├── Offset: 2px
├── Border Radius: matches element
└── Never remove focus indicators!
```

### **ARIA Labels**

```
├── All interactive elements need aria-label or aria-labelledby
├── Icon buttons: aria-label="Action description"
├── Loading states: aria-live="polite"
└── Error messages: aria-describedby
```

### **Color Contrast**

```
├── Body text (#E8ECF0) on black (#020407): 14.2:1 (AAA)
├── Cyan (#7FF7FF) on black (#020407): 14.8:1 (AAA)
├── Light gray (#8B92A0) on black (#020407): 7.4:1 (AA)
└── All interactive elements meet WCAG 2.1 AA standards
```

### **Reduced Motion**

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## **⬡ RESPONSIVE BREAKPOINTS**

```
MOBILE FIRST:
├── Base:    0-639px    (1 column, stacked nav, touch-friendly 44px buttons)
├── Small:   640-767px  (2 columns possible, collapsible sidebar)
├── Medium:  768-1023px (Grid layouts, visible sidebar)
├── Large:   1024-1279px (Full features, multi-column)
└── XLarge:  1280px+    (Wide layouts, max 1200px content)

TOUCH TARGETS:
├── Minimum: 44px × 44px (iOS guidelines)
└── Preferred: 48px × 48px (Android guidelines)
```

---

## **⬡ EXPORT SPECIFICATIONS**

### **For Figma**

1. **Color Styles**: Create color styles for all tokens
2. **Text Styles**: Create text styles for typography scale
3. **Effect Styles**: Create effect styles for shadows and glows
4. **Components**: Build all UI components as Figma components
5. **Auto Layout**: Use Auto Layout for responsive components
6. **Variants**: Use component variants for states (hover, active, disabled)
7. **Documentation**: Add descriptions to all components and styles

### **SVG Export**

- Export at 1x, 2x, 3x for different densities
- Optimize with SVGO
- Ensure all text is converted to paths
- Maintain #7FF7FF and #FF1EA0 color references

### **Design Tokens JSON**

See `design-tokens.json` (created separately) for machine-readable tokens

---

## **⬡ BRAND ASSETS**

### **Logos**

```
├── logo-primary.svg       400×400px  (Hex Coil, full color)
├── logo-white.svg         400×400px  (White version)
├── logo-minimal.svg       200×200px  (Hex only, no text)
├── sigil.svg             200×600px  (Vertical rune)
├── favicon.svg           64×64px    (Browser icon)
└── social-preview.svg    1200×630px (Open Graph image)

CLEAR SPACE:
├── Minimum: 20px around all logos
└── Never place on busy backgrounds

MINIMUM SIZE:
├── Logo Primary: 80px width
└── Sigil: 40px width
```

### **Typography in Brand Context**

```
LOGO LOCKUP:
├── PATCH//HIVE in JetBrains Mono Bold
├── Slash separator: // (not /, not \\)
├── Always uppercase
└── Color: #7FF7FF

TAGLINE:
├── "Modular Synthesis • Deterministic Exploration • Community-Driven Design"
├── Font: JetBrains Mono Regular
├── Size: 12-14px
└── Separators: • (bullet, not dash)
```

---

## **⬡ USAGE GUIDELINES**

### **Do's**

✅ Use hex motifs throughout the interface
✅ Maintain 4:1 contrast ratio minimum for all text
✅ Use JetBrains Mono for all typography
✅ Apply glow effects sparingly for emphasis
✅ Follow the 4px spacing system
✅ Use uppercase labels with letter-spacing
✅ Animate on GPU-accelerated properties only (transform, opacity)
✅ Test with keyboard navigation
✅ Provide loading states for all async actions

### **Don'ts**

❌ Never use colors outside the defined palette
❌ Never use non-monospace fonts
❌ Never remove focus indicators
❌ Never animate width/height properties (causes reflow)
❌ Never use pure white (#FFFFFF) for text
❌ Never use system fonts or custom fonts other than monospace
❌ Never place cyan text on magenta backgrounds (poor contrast)
❌ Never scale the logo non-uniformly
❌ Never rotate the logo

---

## **⬡ IMPLEMENTATION NOTES**

### **CSS Custom Properties**

```css
:root {
  /* Colors */
  --color-cyan: #7FF7FF;
  --color-magenta: #FF1EA0;
  --color-black: #020407;
  --color-success: #00FF88;

  /* Spacing */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;

  /* Typography */
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --font-size-body: 14px;
  --line-height-body: 1.6;

  /* Effects */
  --glow-cyan: 0 0 20px rgba(127, 247, 255, 0.5);
  --transition-fast: 150ms cubic-bezier(0.0, 0.0, 0.2, 1);
}
```

### **Tailwind Config**

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        cyan: '#7FF7FF',
        magenta: '#FF1EA0',
        black: '#020407',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      spacing: {
        xs: '4px',
        sm: '8px',
        md: '16px',
        lg: '24px',
      },
    },
  },
}
```

---

**Built with ⬡ for the PatchHive community**

Version: 1.0 | ABX-Core v1.2 Compliant | Last Updated: 2025-11-25
