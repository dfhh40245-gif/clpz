# CLPZ Design System

## Philosophy

CLPZ is a video creation tool. The design should feel like a premium film studio — dark, confident, content-first. The generated clips ARE the visual center of the product. The interface should retreat into near-invisibility so the user's content dominates.

The design synthesizes patterns from the best creative and SaaS tools but belongs to CLPZ alone.

---

## 1. Visual Theme

**Dark studio.** A near-black canvas (`#0a0a0b`) holds everything. The interface is intentionally invisible — no heavy borders, no shadows, no decorative colors. Generated video clips and thumbnails provide all the color and visual richness. This mirrors how a professional editing suite works: the UI is chrome, the content is the art.

**Confident and minimal.** Every pixel earns its place. No gradient meshes, no decorative orbs, no illustration kits. The product shows what it does through real output.

**Single accent.** Electric amber (`#f0a030`) appears ONLY on the primary action — the Forge button. One filled accent color per viewport. This is the single most important interactive element in CLPZ.

---

## 2. Color System

### Primary Brand
| Token | Hex | Role |
|-------|-----|------|
| `clpz-accent` | `#f0a030` | Primary CTA (Forge), active states |
| `clpz-accent-hover` | `#f5b34d` | Hovered primary CTA |
| `clpz-accent-pressed` | `#d48a20` | Pressed primary CTA |

### Canvas & Surface
| Token | Hex | Role |
|-------|-----|------|
| `clpz-canvas` | `#0a0a0b` | Deepest page background |
| `clpz-surface-1` | `#141416` | Cards, panels, containers |
| `clpz-surface-2` | `#1c1c1f` | Elevated cards, dropdowns, hover |
| `clpz-surface-3` | `#242428` | Modals, dialogs |
| `clpz-surface-inset` | `#0e0e10` | Inset/pressed areas |

### Text
| Token | Hex | Role |
|-------|-----|------|
| `clpz-text-primary` | `#ededed` | Headlines, primary body |
| `clpz-text-secondary` | `#a0a0a8` | Body text, descriptions |
| `clpz-text-tertiary` | `#6b6b73` | Captions, timestamps, metadata |
| `clpz-text-disabled` | `#45454d` | Disabled states |

### Border
| Token | Hex | Role |
|-------|-----|------|
| `clpz-border` | `#222226` | Card borders, dividers |
| `clpz-border-strong` | `#3a3a40` | Input focus, elevated borders |

### Semantic
| Token | Hex | Role |
|-------|-----|------|
| `clpz-success` | `#34d399` | Completed jobs, success states |
| `clpz-error` | `#f87171` | Errors, destructive actions |
| `clpz-warning` | `#fbbf24` | Warnings, pending states |
| `clpz-info` | `#60a5fa` | Informational states |

### Design Principle
Content provides all color. Generated video thumbnails, clip previews, and the user's own media are the primary sources of visual richness in the UI. The interface itself is achromatic — one accent color and a neutral surface scale.

---

## 3. Typography

### Font Family

**Display & UI:** `Inter` (400, 500, 600) — geometric, clean, excellent at all sizes. Open-source, high quality.

**Mono (optional):** `JetBrains Mono` (400) — for timestamps, technical labels, code snippets in advanced UI.

### Hierarchy

| Token | Size | Weight | Line Height | Letter Spacing | Use |
|-------|------|--------|-------------|----------------|-----|
| `display-xl` | 48px | 600 | 1.10 | -1.5px | Hero headlines |
| `display-lg` | 36px | 600 | 1.15 | -1.0px | Section headers |
| `display-md` | 28px | 600 | 1.20 | -0.6px | Card titles |
| `display-sm` | 22px | 600 | 1.25 | -0.3px | Sub-card titles |
| `body-lg` | 18px | 400 | 1.50 | -0.1px | Lead body |
| `body-md` | 16px | 400 | 1.50 | 0 | Default body |
| `body-sm` | 14px | 400 | 1.50 | 0 | Secondary body, nav |
| `caption` | 13px | 500 | 1.40 | 0.3px | Metadata, timestamps |
| `micro` | 11px | 600 | 1.30 | 0.6px | Labels, badges (uppercase) |
| `button` | 14px | 600 | 1.0 | 0 | Button labels |
| `mono` | 13px | 400 | 1.50 | 0 | Timestamps, IDs |

### Principles
- **Display uses weight 600, not 700+** — confident but not aggressive
- **Negative tracking on display** (-0.3px to -1.5px) — tightens headlines into editorial density
- **Body at weight 400** — never bold at body size unless emphasizing
- **Uppercase + positive tracking for labels** — section eyebrows, badges, micro labels
- **Inter is the only font** — no switching families for marketing vs. app
- **Mono for technical contexts only** — timestamps, IDs, code

---

## 4. Spacing

### Base Unit: 4px

| Token | Value | Use |
|-------|-------|-----|
| `space-xxs` | 4px | Inline tight gaps |
| `space-xs` | 8px | Component internal gaps |
| `space-sm` | 12px | Form input padding, small gaps |
| `space-md` | 16px | Card internal padding, body gaps |
| `space-lg` | 24px | Section internal padding |
| `space-xl` | 32px | Card padding, major gaps |
| `space-2xl` | 48px | Section spacers |
| `space-3xl` | 64px | Major section breaks |
| `space-section` | 96px | Marketing section rhythm |

### Principles
- **Dense in the app, generous in marketing.** The Forge dashboard uses 16-24px internal spacing. Marketing sections use 64-96px vertical rhythm.
- **8px horizontal rhythm.** Text aligns to an 8px grid for visual consistency.
- **Cards at 24px internal padding.** Enough breathing room without wasting space.

---

## 5. Shapes

### Border Radius

| Token | Value | Use |
|-------|-------|-----|
| `radius-xs` | 4px | Inline tags, small chips |
| `radius-sm` | 6px | Form inputs, small UI elements |
| `radius-md` | 8px | Buttons, standard containers |
| `radius-lg` | 12px | Cards, panels, clip previews |
| `radius-xl` | 16px | Large cards, hero containers |
| `radius-pill` | 9999px | Primary CTA (Forge button), badges |
| `radius-full` | 9999px | Circular elements, avatars |

### Design Decision: Pill for Primary CTA Only
The Forge button uses `radius-pill` (9999px) — this is the single most important interactive element. All other buttons use `radius-md` (8px). This creates a clear visual hierarchy: the Forge button is special.

---

## 6. Elevation & Depth

On dark surfaces, shadows are invisible. Depth is communicated through:

1. **Surface ladder:** `canvas` → `surface-1` → `surface-2` → `surface-3`
2. **Hairline borders:** 1px `clpz-border` on cards
3. **Content brightness:** Bright video thumbnails naturally float above dark surfaces

### Border Treatments
| Level | Treatment | Use |
|-------|-----------|-----|
| Flat | No border | Canvas background |
| Contained | 1px `clpz-border` | Cards, panels, inputs |
| Elevated | 1px `clpz-border-strong` | Focused inputs, active elements |
| Modal | 1px `clpz-border` + `surface-3` bg | Dialogs, dropdowns |

### No Shadows
Do not use `box-shadow` on dark surfaces. The dark background IS the depth. If shadows are needed for floating elements (dropdowns, tooltips), use a very subtle `0 4px 24px rgba(0,0,0,0.4)`.

---

## 7. Components

### Buttons

**Primary (Forge)** — The most important button in CLPZ.
- Background: `clpz-accent` (#f0a030)
- Text: `#0a0a0b` (dark on light)
- Typography: `button` (14px / 600)
- Radius: `radius-pill` (9999px)
- Padding: 12px 24px
- Height: 44px minimum

**Secondary**
- Background: `clpz-surface-1`
- Text: `clpz-text-primary`
- Typography: `button` (14px / 600)
- Radius: `radius-md` (8px)
- Border: 1px `clpz-border`
- Padding: 10px 20px

**Ghost**
- Background: transparent
- Text: `clpz-text-secondary`
- Typography: `button` (14px / 600)
- Radius: `radius-md` (8px)
- Padding: 10px 20px

**Destructive**
- Background: `clpz-error` (#f87171)
- Text: `#0a0a0b`
- Typography: `button` (14px / 600)
- Radius: `radius-md` (8px)

### Cards

**Standard Card**
- Background: `clpz-surface-1`
- Border: 1px `clpz-border`
- Radius: `radius-lg` (12px)
- Padding: 24px

**Clip Preview Card**
- Background: `clpz-surface-1`
- Border: 1px `clpz-border`
- Radius: `radius-lg` (12px)
- Padding: 0 (content fills edge-to-edge)
- Contains: video thumbnail (16:9), title, duration, action buttons

**Pricing Card**
- Background: `clpz-surface-1`
- Border: 1px `clpz-border`
- Radius: `radius-lg` (12px)
- Padding: 32px

**Pricing Card Featured**
- Background: `clpz-surface-2`
- Border: 1px `clpz-accent` (amber)
- Radius: `radius-lg` (12px)
- Padding: 32px

### Forms

**Text Input**
- Background: `clpz-surface-inset`
- Text: `clpz-text-primary`
- Border: 1px `clpz-border`
- Radius: `radius-sm` (6px)
- Padding: 10px 14px
- Height: 40px
- Focus: border → `clpz-accent`

**URL Input (YouTube)**
- Same as text input, with a play icon prefix
- Validation states: green border (valid URL), red border (invalid)

### Navigation

**Top Nav**
- Background: `clpz-canvas`
- Height: 56px
- Border-bottom: 1px `clpz-border`
- Left: CLPZ wordmark
- Center: nav links
- Right: credit display, account, logout

**Tab Navigation**
- Background: transparent
- Active: bottom border `clpz-accent` 2px
- Inactive: `clpz-text-tertiary`

### Status Indicators

**Job Status Pill**
- Queued: `clpz-surface-2` bg, `clpz-text-secondary` text
- Processing: `clpz-accent` bg (pulsing), dark text
- Done: `clpz-success` bg, dark text
- Error: `clpz-error` bg, dark text
- Radius: `radius-pill`

**Credit Display**
- Background: `clpz-surface-1`
- Border: 1px `clpz-border`
- Radius: `radius-md`
- Icon + count + label

---

## 8. Layout Principles

### Marketing Website

**Hero:** Full-width dark canvas. Display headline in `display-xl`, subtitle in `body-lg`, single Forge CTA in amber pill. Real clip preview below the hero — the product speaks for itself.

**Feature sections:** Alternate between `clpz-canvas` and `clpz-surface-1` backgrounds. Each section explains one capability with a real product screenshot or clip example.

**Pricing:** 3-up card grid. Featured tier uses amber border.

**Footer:** Dense link grid on `clpz-canvas`. `clpz-text-tertiary` text.

### Dashboard (Forge Interface)

**Layout:** Sidebar (fixed, 240px) + main content area. Sidebar contains: Forge, Clips, Account, Credits.

**Forge page:** YouTube URL input or upload zone → Forge button → processing status → clip results grid.

**Clips page:** Grid of generated clips (3-up on desktop, 2-up on tablet, 1-up on mobile).

**Job progress:** Inline progress bar with stage label (transcribing, analyzing, rendering).

### Section Rhythm
- Marketing: 96px between sections
- Dashboard: 24px between sections, 16px between cards

---

## 9. Responsive Breakpoints

| Name | Width | Key Changes |
|------|-------|-------------|
| Mobile | < 640px | Single column, stacked cards, hamburger nav |
| Tablet | 640–1024px | 2-column grid, sidebar collapses |
| Desktop | 1024–1440px | Full layout, 3-column grid |
| Wide | > 1440px | Content caps at 1280px, centered |

### Touch Targets
- All interactive elements: minimum 44×44px on mobile
- Buttons: minimum 40px height
- Nav items: generous padding for tap targets

### Collapsing Strategy
- Navigation: full links → hamburger below 768px
- Card grids: 3-up → 2-up → 1-up
- Display type: 48px → 36px → 28px
- Sidebar: fixed → overlay → hidden

---

## 10. Interaction Patterns

### Transitions
- Duration: 150ms for micro-interactions (hover, focus)
- Duration: 200ms for state changes (tab switches, card reveals)
- Easing: `ease-out` for entries, `ease-in-out` for exits

### Hover States
- Cards: border brightens to `clpz-border-strong`
- Buttons: background shifts (primary lightens, secondary brightens)
- Links: text color shifts to `clpz-accent`

### Focus States
- 2px `clpz-accent` outline with 2px offset
- Never remove focus indicators — accessibility is mandatory

### Loading States
- Skeleton screens: `clpz-surface-2` animated shimmer
- Progress bars: `clpz-accent` fill on `clpz-surface-inset`
- Spinning indicators: `clpz-accent` ring

---

## 11. Do's and Don'ts

### Do
- Keep the interface dark and invisible — content is king
- Use the amber accent ONLY on the Forge button and critical actions
- Show real generated clips as the primary visual element
- Use tight negative tracking on display headlines
- Maintain 44px minimum touch targets on mobile
- Use the surface ladder for visual hierarchy
- Keep Inter for all text — single typeface commitment

### Don't
- Don't use decorative gradients, orbs, or illustrations
- Don't use multiple accent colors
- Don't add shadows to dark surfaces (they're invisible)
- Don't use pill shape on anything except the Forge button
- Don't use weight 700+ on display headlines
- Don't use pure black (#000000) — always use `clpz-canvas` (#0a0a0b)
- Don't put body text in monospace
- Don't create marketing sections without showing real product output

---

## 12. Implementation Notes

### CSS Custom Properties
All tokens should be defined as CSS custom properties on `:root` for easy theming and future light mode support.

### Current Frontend
The current `clpz.html` uses inline styles with a dark theme already aligned to this system. The design system provides tokens and principles for consistent evolution.

### Future
- Components should be extracted to a shared component library as CLPZ grows
- The design system should be tested with real content (generated clips) not placeholder images
- Accessibility audit should be performed before production launch
