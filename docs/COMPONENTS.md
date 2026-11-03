# PatchHive Component Library

**React Components and Visual Assets**

This document describes the available UI components and how to use them.

---

## React Components

The shared components live in `frontend/src/components/`. The ones most screens use:

- **Skeletons** (`Skeletons.tsx`): placeholders in the shape of what is loading (a list, a rail, the signal chain, a readout figure), with one delayed status line for screen readers.
- **LoadFailure** (`LoadFailure.tsx`): what didn't load, why in one sentence (from `lib/loadError.ts`), and Retry. It is an alert, never an empty state.
- **ShowMore** (`ShowMore.tsx`): the next page of a list the API pages.
- **Toast** (`Toast.tsx`, with `lib/useToast.ts`): one polite message at the foot of the screen, with an optional action such as Undo that stays until used and also runs with Ctrl or Cmd+Z.
- **Tabs** (`Tabs.tsx`): a keyboard-correct tab list (arrows, Home, End, one tab stop).
- **RigRail**, **PatchRail** and **builder/PlacementRail**: a rig drawn to HP scale, a patch's cables on it, and the editable rail in the builder.

---

## SVG Assets

### Logo System

#### Primary Logo: The Hex Coil

**File**: `docs/assets/logo-primary.svg`

```html
<!-- HTML -->
<img src="docs/assets/logo-primary.svg" alt="PatchHive" width="200">
```

```tsx
// React
import logo from '@/assets/logo-primary.svg';
<img src={logo} alt="PatchHive" />
```

**Specifications**:
- Size: 400×400px
- Format: SVG (scalable)
- Background: Deep Synth Black (#020407)
- Primary color: Hive Cyan (#7FF7FF)

**Features**:
- Hexagon frame with glow effect
- Honeycomb pattern interior
- Three CV pathway spirals
- Central luminous oscillator core
- Voltage markers at vertices

---

#### Secondary Mark: The Patch Sigil

**File**: `docs/assets/sigil.svg`

```html
<img src="docs/assets/sigil.svg" alt="PatchHive Sigil" height="300">
```

**Specifications**:
- Size: 200×600px (vertical)
- Represents: Oscillator → Filter → Amplifier signal chain

**Use cases**:
- Splash screens
- Loading screens
- Vertical banners
- App icons (tall format)

---

### Icon Set

#### Module Type Icons

**File**: `docs/assets/icons/module-types.svg`

Contains 10 module type icons:

1. **VCO** (Voltage Controlled Oscillator) - Circle with sine wave
2. **VCF** (Voltage Controlled Filter) - Chevron cascade
3. **VCA** (Voltage Controlled Amplifier) - Expanding triangle
4. **ENV** (Envelope) - ADSR curve
5. **LFO** (Low Frequency Oscillator) - Slow sine with loop
6. **SEQ** (Sequencer) - Step grid
7. **MIX** (Mixer) - Converging lines
8. **FX** (Effects) - Spiral trails
9. **UTIL** (Utility) - Junction node
10. **NOISE** (Noise Generator) - Random static pattern

#### Extracting Individual Icons

To extract a single icon for use:

```tsx
// React component for VCO icon
export const VCOIcon = ({ size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg">
    <circle cx="48" cy="48" r="40" fill="none" stroke="#7FF7FF" strokeWidth="2.5" />
    <path d="M 18,48 Q 33,28 48,48 T 78,48" fill="none" stroke="#7FF7FF" strokeWidth="2" />
    <circle cx="48" cy="48" r="6" fill="#7FF7FF" opacity="0.8" />
  </svg>
);
```

---

### Marketing Assets

#### Header Banner

**File**: `docs/assets/header-banner.svg`

```html
<img src="docs/assets/header-banner.svg" alt="PatchHive" width="100%">
```

**Specifications**:
- Size: 1200×300px
- Use: README headers, website hero sections

---

#### Social Preview

**File**: `docs/assets/social-preview.svg`

**Specifications**:
- Size: 1200×630px
- Use: Open Graph, Twitter cards, Discord embeds

**GitHub Setup**:
```yaml
# .github/social-preview.yml
image: docs/assets/social-preview.svg
```

---

#### Favicon

**File**: `frontend/public/favicon.svg`

```html
<!-- HTML -->
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
```

**Vite Configuration** (already set up):
```ts
// vite.config.ts
export default defineConfig({
  // Favicon is automatically served from public/
})
```

---

## CSS Utilities

### Color Variables

Add to your global CSS:

```css
:root {
  --hive-cyan: #7FF7FF;
  --deep-synth-black: #020407;
  --pulse-amber: #EBAF38;
  --mod-voltage-blue: #2E7CEB;
  --signal-magenta: #FF1EA0;
  --graphite-grey: #1A1D21;
}
```

### Component Classes

```css
/* Hex border style */
.hex-border {
  border: 2px solid var(--hive-cyan);
  clip-path: polygon(30% 0%, 70% 0%, 100% 50%, 70% 100%, 30% 100%, 0% 50%);
}

/* Glow effect */
.glow-cyan {
  box-shadow: 0 0 10px rgba(127, 247, 255, 0.5);
  filter: drop-shadow(0 0 8px rgba(127, 247, 255, 0.3));
}

/* Signal pulse animation */
@keyframes signal-pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.signal-active {
  animation: signal-pulse 2s ease-in-out infinite;
}
```

---

## Usage Examples

### Loading State

```tsx
import LoadFailure from '@/components/LoadFailure';
import { ListSkeleton } from '@/components/Skeletons';

function ModulePage() {
  if (state === 'loading') return <ListSkeleton label="Loading modules…" />;
  if (state === 'error') return <LoadFailure what="The module catalog" error={error} onRetry={reload} />;
  return <ModuleList />;
}
```

### Module Type Badge

```tsx
function ModuleTypeBadge({ type }: { type: string }) {
  const iconMap: Record<string, string> = {
    VCO: '○', // Use actual icon component
    VCF: '⌄',
    VCA: '△',
    // ... etc
  };

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.5rem',
      padding: '0.25rem 0.75rem',
      border: '1px solid #7FF7FF',
      borderRadius: '4px',
      color: '#7FF7FF',
      fontFamily: 'monospace',
      fontSize: '0.875rem'
    }}>
      <span>{iconMap[type] || '◆'}</span>
      <span>{type}</span>
    </span>
  );
}
```

---

## Animation Guidelines

### Performance

- All animations use CSS transforms and opacity (GPU-accelerated)
- No layout-triggering properties (width, height, top, left)
- Animations respect `prefers-reduced-motion`

### Timing

- **Fast**: 0.2s (hover states, clicks)
- **Medium**: 0.5s (transitions, fades)
- **Slow**: 1-3s (pulsing, breathing)
- **Infinite**: Loops for loading states

### Easing

```css
/* Standard transitions */
transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

/* Smooth pulse */
animation: pulse 2s ease-in-out infinite;

/* Linear rotation */
animation: rotate 3s linear infinite;
```

---

## Accessibility

### Keyboard Navigation

All interactive components support:
- Tab navigation
- Enter/Space activation
- Escape to close modals

### Screen Readers

Loading states announce once through the skeleton's status line; failures are alerts (`LoadFailure`); results and Undo arrive through the toast's polite live region.

### Reduced Motion

`frontend/src/styles/base.css` ends every animation and transition at once under `prefers-reduced-motion: reduce`, so components need no check of their own.

---

## Testing Components

### Visual Testing

There is no Storybook. Every screen is checked in a real browser by the design guard, `frontend/tests/ui/design.spec.ts`: axe (colour contrast included), nothing past the viewport, and each screen's signature drawing, in both themes at 1440 and 375 px.

### Unit Testing

```tsx
import { render, screen } from '@testing-library/react';
import LoadFailure from './LoadFailure';

test('says what did not load, and why', () => {
  render(<LoadFailure what="Your credits" error={{ code: 'ERR_NETWORK' }} />);
  expect(screen.getByRole('alert')).toHaveTextContent("Your credits didn't load.");
});
```

---

## Future Components

Planned for Phase 2:

- [ ] **ModuleCard** - Display module with specs and ports
- [ ] **RackVisualizer** - Interactive rack layout
- [ ] **PatchDiagram** - SVG patch connection viewer
- [ ] **WaveformDisplay** - Animated waveform component
- [ ] **ConnectionCable** - Animated patch cable
- [ ] **SignalMeter** - VU meter style indicator
- [ ] **HPCounter** - Remaining HP display
- [ ] **PowerMeter** - Power draw visualization

---

For more information, see:
- [Brand Guidelines](BRAND_GUIDELINES.md)
- [Architecture Documentation](ARCHITECTURE.md)
- [Main README](../README.md)
