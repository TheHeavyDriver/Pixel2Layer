# Pixel2Layer — Frontend Design Specification

This document specifies in detail how the Pixel2Layer frontend should look and behave. It is the visual/UX contract for `apps/web` and should be read with `architecture.md` (§3.1, §4) and `prd.md`. It covers every screen, layout, component, interaction, and state — from a single pixel of spacing to the full reconstruction flow.

---

## 1. Design language

### 1.1 Product persona
A professional but approachable design tool. Think Figma's clarity + Canva's friendliness. Dense where power users need density (layers/properties panels), calm where novices land (upload, dashboard).

### 1.2 Visual style summary
| Aspect | Spec |
|--------|------|
| Aesthetic | Clean, flat UI with subtle elevation; no skeuomorphism, no heavy shadows |
| Corners | 8px radius on cards/panels, 10px on buttons 44px+ tall, 14px on modals |
| Density | Panels pack tightly (28px rows) — users are editing, not browsing |
| Motion | 150–220ms ease-in-out for hovers/panel toggles; 300ms for modals/progress |
| Noise | No gradients flourishes, no decorative patterns, no emoji in the product UI |
| Language | Clear, specific English; confidence values as `%`; errors explain how to fix |

### 1.3 Color tokens
| Token | Value | Usage |
|-------|-------|-------|
| `bg-base` | `#0F0F10` | App background (dark mode default) |
| `bg-surface` | `#1A1B1D` | Panels, modals, dropdowns |
| `bg-raised` | `#232427` | Inputs, hover states, toolbars |
| `border-default` | `#2E2F33` | Panel separators, outlines |
| `border-strong` | `#3D3F45` | Focus rings, active borders (a11y) |
| `text-primary` | `#F4F4F5` | Headings, layer names, canvas tooltips |
| `text-secondary` | `#A1A1AA` | Labels, metadata, hints |
| `text-muted` | `#64646C` | Disabled, placeholders |
| `accent` | `#6C8EFF` | Selection, primary buttons, active tabs, focus |
| `accent-hover` | `#5675E8` | Primary button hover |
| `success` | `#4CC38A` | Job done, confidence ≥ 80%, save confirmed |
| `warning` | `#E8B04B` | Confidence 50–79%, degraded names |
| `danger` | `#E5484D` | Errors, delete, failed jobs |
| `info` | `#5E8BC9` | "Approximate segmentation" labels, hints |
| `canvas-drop` | `rgba(17,18,20,0.97)` | Canvas viewport backdrop |

Light theme is **out of scope for v0.1–v0.5** (see §8.2); dark default only.

### 1.4 Typography
- Family: system stack for UI (`Inter` loaded optionally). No display font in the chrome UI — the *artboard content* uses design fonts, which are a concern of the scene graph, not chrome.
- Type scale:

| Role | Size / Weight / Letter-spacing |
|------|-------------------------------|
| Display (empty states, big modals) | 24px / 600 / -0.02em |
| H1 (screen headers) | 20px / 600 / -0.02em |
| H2 (panel section titles) | 13px / 600 / 0 |
| Body | 13px / 400 |
| UI label / caption | 12px / 500 |
| Micro (badges, confidence) | 11px / 600 / 0.04em (uppercase) |
| Mono (value readouts, hex codes) | 12px / `ui-monospace` |

### 1.5 Iconography
- 16px stroke icons (Lucide/Radix set) at 1.5px stroke, `currentColor`. Toolbar icons 18px. No filled icons except the selection/active indicator dot (8px).
- Confidence gauge icon variants: solid check (done), half-shield (warning), broken-shield (danger).

### 1.6 Spacing & layout grid
- Base unit 4px. Panel padding 12–16px; toolbar 8px; gap between sidebar columns 8px.
- Default app frame: left **Layers** 240px, center **Canvas** flexible, right **Properties** 280px, top **Toolbar** 44px, bottom **Status bar** 28px. (See §3.)

### 1.7 Buttons & controls
- Variants: `primary` (accent bg, white text), `secondary` (bg-raised, border), `ghost` (transparent, hover bg-raised), `danger` (danger text/outline). Heights: 28px (toolbar) / 32px (inline) / 40px (forms, upload CTA).
- Buttons 28px+ display tooltips on hover (150ms delay).
- States: default, hover (bg wash), active (translate-y 0.5px + darker), disabled (40% opacity), loading (inline spinner 14px).
- Focus ring: 2px `border-strong` + 2px accent glow, always visible, never removed silently.

### 1.8 Scrollbars, selection, focus
- Scrollbars: 8px, thumb `border-strong`, track transparent, only visible on hover.
- Canvas selection outlines: **2px accent with 4 white corner handles** (Fabric controls themed via CSS overrides); dashed bounding box while dragging.
- Single-click to select, double-click text to edit in place, Escape deselects, Ctrl/Cmd+Z undo.

---

## 2. Global chrome & navigation

### 2.1 App shell (authenticated)
```
┌───────────────────────────────────────────────────────────────┐
│ Topbar 44px                                                  │
│  [Logo]  [→ Editor]  [Projects]  [Templates]   [avatar ▾]    │
├────────┬───────────────────────────┬─────────────────────────┤
│ Layers │                         Canvas │ Properties          │
│ 240px  │                     flex-grow  │ 280px               │
│        │                             (checkerboard bg)       │
├────────┴───────────────────────────┴─────────────────────────┤
│ Status bar 28px  [stage name] [progress] [confidence] [saved]│
└───────────────────────────────────────────────────────────────┘
```

- **Logo** — 20×20 mark (two stacked layers / a "pixel becoming layers" glyph) + wordmark "Pixel2Layer", hidden below 1024px.
- **Topbar nav item states:** active = accent underline (2px, inset 12px); hover = bg wash.
- **Avatar menu:** profile, settings (future), sign out.
- Editor is full-screen framed; dashboards are regular routed pages (Settings gets stack-based access or collapse-topbar layout, see §8.1).

### 2.2 Shared feedback primitives
- **Toast** — bottom-right, 320px, bg-surface + border, 32px safe. Auto-dismiss: success 3.5s, info 5s; error persists until dismissed. Icons per severity.
- **Inline spinner** — 14px, track `border-default`, arc accent.
- **Modal** — centered, max-width 480px (min 320px), 14px radius, overlay `rgba(0,0,0,0.5)` + blur(2px), CLOSE on overlay click, Esc, and X button.
- **Empty state** — centered illustration (inline SVG, 64px stroke), 24px message, 13px muted hint, one primary action + one secondary.

---

## 3. Screens in detail

### 3.1 Home / Product landing (public)
```
┌──────────────────────────────────────────────────────────────┐
│  nav: [logo] … [Sign in]  [Get started →]                    │
│                                                               │
│         H1(40px): "Recover the design behind the image"       │
│         sub(16px secondary): drop a flat poster → get back    │
│         text, shapes, vectors, layers — fully editable.       │
│         [Upload an image]  [or]  [Try a sample]  [waveform]   │
│                                                               │
│  [before/after interactive demo card]                         │
│  three feature cards: Editable text · Real shapes · Vectors   │
│  footer terms/privacy                                         │
└──────────────────────────────────────────────────────────────┘
```
- **Upload zone** on the landing hero accepts drag-drop + click. Dropping there transitions straight into the reconstruction flow (§4) — the same upload used everywhere.
- Demo card: toggle "Original ⇄ Reconstructed" with a 300ms crossfade; pointer interactions show layer highlighting on hover.
- This page is static (SSR). No chat, no prompt box anywhere.

### 3.2 Auth (Sign in / Sign up)
- Centered card 400px on `bg-base`. Tabs `Sign in` / `Sign up`.
- **Sign in:** email, password, `[Continue]`, divider "or", OAuth buttons GitHub + Google (secondary, 40px), "Forgot password?" link.
- **Sign up:** name (optional single field), email, password (show/hide eye), confirmation sent screen.
- Validation inline under fields (danger text 12px). Submit → button loading state.
- Post-auth redirect: back to the page that triggered sign-in, else `/projects`.

### 3.3 Projects dashboard (`/projects`)
```
┌─────────────────────────────────────────────────────────────┐
│ Topbar: [logo] [Projects] [Templates]          [+ New ▾]    │
│                                                              │
│  "Projects" (H1)          [search ⌕]  [sort ▾]               │
│  ┌──────────┬──────────┬──────────┐                          │
│  │ Preview  │ Preview  │  + New   │  ← card grid, 4 cols    │
│  │ name     │ name     │  upload  │    (min 240px each)     │
│  │ updated  │ updated  │  design │                          │
│  │ ▸▸▸ menu │ ▸▸▸ menu │          │                          │
│  └──────────┴──────────┴──────────┘                          │
│  (each card = rendered canvas thumbnail 4:3, lazy-loaded)    │
└─────────────────────────────────────────────────────────────┘
```
- Card menu (`▸▸▸`): Open, Rename, Duplicate, Share, Export, Version history, Delete (danger, confirm modal).
- Search filters by name. Sort: Last edited / Created / Name.
- Create via `+ New` → opens Upload modal (§4.1). Card click → opens editor.
- New UX: after upload + reconstruction, a "Save as project?" sheet appears (see §4.6).

### 3.4 Templates gallery (`/templates`)
- Same grid visual as Projects but read-only cards labeled "Template".
- Top actions: `[Import image →]` and category filter chips (All / Social / Print / Posters).
- **Hover overlay on template card:** "Use as start" — clicking creates a draft project from the template's scene graph, opens editor immediately.

### 3.5 Editor (core screen) — full spec in §5

### 3.6 Shared / public link (`/share/{token}`)
- Read-only variant: hide toolbar editing actions (move/resize still OK to preview), no save, topbar shows "Shared with you · [Open in editor ↗]" if token grants edit.
- Read link: properties read-only; layers read-only; canvas selectable for inspection only; banner strip: `Info` icon "This is a shared design · view only".
- Edit link: full editor; auto-saves to the *owner's* project when the owner offers it; no project listing access, no history.

### 3.7 Export & Save dialogs (see §5.8)

---

## 4. The reconstruction flow (upload → editable design)

This is the product's signature moment. It must feel fast, transparent, and trust-building.

### 4.1 Upload modal
- Opens from Landing hero, Dashboard `+ New`, Editor toolbar `Import`, or batch entry.
- Body: dashed dropzone (2px `border-strong`, 88px tall), "Drag & drop an image" + "PNG, JPG, JPEG, WebP · up to 25MB" microcopy, and `browse files` ghost button. Paste-from-clipboard also accepted.
- Hover: border → accent, bg wash. Drag-over: accent border + accent wash, "Drop to upload".
- On select → **confirm card**: preview thumb 96×96 4:3, file name, size, `[Cancel]` `[Reconstruct →]`.

### 4.2 Inline upload (drag-and-drop from launcher states)
- On Projects/Templates, dropping a file anywhere on the backdrop opens the same confirm card in an overlay; editor drops become "Add as new import?" — always a new reconstruction, never silently merged.

### 4.3 Reconstruction progress screen
Full-page takeover (bg-base), centered 480px column:

```
  [animated scan of the uploaded image fading to layers glyph]
  "Reconstructing your design" (H1 24px)
  Active stage (H2 + micro progress):
     ● Detecting text           ✓ 100%
     ● Finding shapes           ▸ 60%  ← current, accent pulse
     ● Extracting colors        ○ 0%
     ● Segmenting photos        ○ 0%    (hidden until v0.4)
     ● Building layers          ○ 0%
  Overall: [progress bar 8px, accent fill + % readout]
  microcopy: "Simple posters take ~5s. Complex photos can take longer."
  [ Cancel ]  ghost, top-right of panel
```

- Stage list is **a live checklist** fed by SSE: pending (hollow circle), running (pulsing accent ring + %), done (success check).
- Non-dismissable except Cancel; Cancel asks "Keep the original image? It stays in your uploads." (danger confirm).
- **Failure state:** turn panel bg `danger/8`, show the failed stage, "Something went wrong analyzing this image. [Retry] [Report]" — Retry re-enqueues a job.

### 4.4 Completion → Save-as-project sheet
Centered bottom sheet (from modal position, animated up 300ms):

```
  "Your image is now editable"  ✓ success
  [preview of reconstructed canvas thumb 400px]
  "Design"  [text 2]  [circle]  [image]   — count chips
  Overall reconstruction confidence:  [94%]  (micro note:
    "Elements below 70% may need a quick check.")
  [ Open in editor  (primary) ]
  [ Save project  (secondary, default name = file stem) ]
```

- Choosing "Open in editor" (guest) enters editor in draft mode; Save prompts auth if needed.
- Confidence summary links to editor's Confidence view (§5.6).

### 4.5 Batch upload (Phase 4)
- Multipick entries listed with per-item status from SSE (idle → reconstructing % → done/failed) in a 96px-tall list; button row: `[Open]` (per done item), bottom: `[Open all as projects]` `[Cancel]`.

### 4.6 Editor entry
- Draft mode banner (top, under topbar): "Unsaved reconstruction · [Save ↧]" (success if signed out: "Sign in to save").
- Draft scene graph lives in-memory; refresh warns "Your reconstruction isn't saved."

---

## 5. The Editor (detailed spec)

### 5.1 Layout & regions
```
┌───────────────────────────────────────────────────────────────┐
│ Toolbar 44px:                                                │
│ [↩][↪] │ [Select][Hand] │ [Text][Shape▾][Image][Vector path] │
│   zoom [−][+][fit]    [Import ▾] [Share] [Save] [Export▾]     │
├────────┬───────────────────────────────┬─────────────────────┤
│ Layers │ Canvas (checkerboard)        │ Properties          │
│ 240px  │   object file: [tablet frame] │  non-selected:      │
│        │                               │  Canvas tab         │
├────────┴───────────────────────────────┴─────────────────────┤
│ Status 28px: [stage/maintenance] [labels] [zoom%] [autosave] │
└───────────────────────────────────────────────────────────────┘
```

### 5.2 Canvas & artboard
- **Viewport:** dark `canvas-drop` backdrop. White artboard is rendered as the effective canvas (scene graph `canvas.background`); if transparent, show checkerboard behind (10px squares `#202124`/`#26272B`).
- Artboard dimensions from scene graph (e.g., 1920×1080); **fit-to-view** on open (16px margin).
- **Zoom:** wheel (cursor-centered), pinch, `Ctrl +/-`, `<− − +>` toggles at 8 steps (0.25×–4×), "Fit" centers artboard at max-fit.
- **Pan:** space+drag, middle-mouse drag, or `Hand` tool (V for select, H for hand).
- **Rulers/guides:** v0.2 physical rulers optional (see §8.2); smart guides + center lines appear on drag (accent, 1px, dashed), snapping distance 6px.
- **Multi-select marquee:** drag empty area draws accent 1px marquee; `Shift` toggles membership.
- **Selection:** topmost object under cursor on click; `Shift/click` adds/removes; selecting grouped object = the group as one handle set (with sub-select on double-click, releases as the child's handles).

### 5.3 Object manipulation controls (Fabric overlay)
- Handles: 4 corners (resize) + 4 edges (strech) + rotate handle (offset above top-center, 16px from box).
- **Resize:** corner = proportional scale always (preserve aspect); edge = scale that axis only. Ctrl = ignore? No — Ctrl reserved for **skip snapping**. Alt = resize from center | rotate snaps to 1°.
- **Rotate:** drag outside rotates around center; snaps at 15° increments with snap preview line; holding Alt frees snap.
- **Bounding box:** accent outline + white handles (inverse-contrast outline around handles when over light artboard).
- Double-click behaviors: text → inline edit caret; image → enters "mask/crop" mode (§5.5); path → enters path edit (§5.7); other → no-op.
- **Group (Ctrl+G)/Ungroup(Ctrl+Shift+G):** grouped box shows one handle set; group renamed to "Group N".

### 5.4 Layers panel (left)
```
Layers  [+]
┌────────────────────────────────────────────┐
│ ⌕ filter                          [▸ options] │
│ 👁 🔒 [■ Background        ]   [confidence 95%]│
│ 👁    [A Heading          ]            [86%]│  ← row hover shows 👁/🔒 toggles
│       [  A Subtitle       ]            [78%]│
│ 👁    [◯ Circle           ]            [62%]│ ← low: amber chip + warning dot
│ +    [🖼 Product image ▤ ✕]                    │
│      (drag rows to reorder; indent = group)  │
└────────────────────────────────────────────┘
```
- **Row:** eye (toggle), lock, type glyph, edited name (15px ellipsis), confidence chip.
- **Actions per row** (hover ▸▸▸): Rename (inline, F2), Duplicate, Delete (danger, no confirm for single), Lock/Unlock.
- **Reorder:** drag handle (6 dots); drop line indicator accent. Auto-scroll on edge drag.
- **Grouping in panel:** children indent 16px; group chevron + a single eye/lock applies to all members (child overrides show as half-state eye).
- **Bottom toolbar:** `[＋ Add layer ▾] [Select all] [Top/bottom shortcuts]`.
- **Filter** matches name or type. **Confidence chip:** ≥80 success, 50–79 warning, <50 danger; click → focus that element + open confidence detail.
- **Selection sync:** clicking a panel row selects on canvas & vice versa; visibility syncs both ways.

### 5.5 Properties panel (right) — schema-driven
Collapsible sections per element type, auto-open with keys present in the schema.

**Canvas tab (nothing selected):**
- Canvas size (W × H numeric inputs, apply). Background color swatch.
- Export quick actions: `[PNG] [JPG] [SVG] [PDF(disabled until v0.5)]` (labels §5.8).

**Text object:**
| Section | Controls |
|---------|----------|
| Content | editable multiline textarea (2–4 rows, monospace at 13px), char/line count |
| Font | family dropdown (design fonts registry, searchable) + weight select (slider 100–900 + preview glyph) |
| Size | numeric + font-size slider |
| Style | italic toggle, underline toggle, letter-spacing stepper (`±0.5`, unit px) |
| Alignment | L / center / R / justify segmented + line-height stepper |
| Text color | swatch row + hex input + opacity % |
| Transform | X, Y, W, H numeric inputs; rotation stepper + degree input; flip buttons ↔↕ |
| Opacity | slider % |
| Appearance | "Convert to shape/outline" (danger-ghost, confirm: "This text becomes a vector path and is no longer editable text.") |

**Shape (rectangle/circle/ellipse/line/polygon/shape):**
| Section | Controls |
|---------|----------|
| Fill | color swatch + eyedropper + opacity; gradient editor (two-stop linear/radial, stop color/pos editor) |
| Stroke | color swatch, width stepper, dash style select; stroke alignment (inset/center/outset) |
| Corners | radius stepper + "round all" toggle (rect/rounded-rect only) |
| Transform, Opacity | as text (§5.5) |
| Confidence | detail chip (see §5.6) if below threshold |

**Image object:**
| Section | Controls |
|---------|----------|
| Source | thumb, "Replace image…" |
| Fit | `Fit` / `Fill` / `Stretch` segmented; aspect-lock toggle |
| Crop/Mask | `Crop` button → enters crop mode (see §5.5.1) |
| Filters | brightness, contrast, saturaion sliders (−100…100), "Clear" |
| Transform, Opacity | as above |

**5.5.1 Crop/mask mode (image):** overlay darkens area outside crop; 8 handles; `Enter/Apply` ✓ `Esc/Cancel` ✗; values as W/H inputs. Mask = shapes drawn on top clipping the image.

**Vector/path object:**
| Section | Controls |
|---------|----------|
| Fill | as shape |
| Stroke | as shape |
| Editing | `[Edit path]` toggle → path mode (§5.7) |
| Confidence | chip |

**5.5.2 Alignment tools** (multi-select): Align left/center/right, top/middle/bottom, Distribute horizontal/vertical, "Same width/height" — controls in a `Distribute` sub-tab or toolbar flyout.

### 5.6 Confidence UI
Per **overall** (status bar center, chip + %):
```
[shield ✓] Reconstruction 94%   → click opens panel:
  Text 98% ██████████
  Shapes 97% ██████████
  Images 89% █████████
  Logo/Vector 92% █████████
  Background 95% █████████
  Overall 94% █████████
  note: "Lower-scoring areas may need manual tweaks."
  [Review low-confidence (3)]
```
Per **element**: small chip in Layers (§5.4) + a dashed amber outline on canvas (only while "Show confidence" is on in status bar, default off; low elements always get an amber dot) + tooltip on hover: "Confidence 62% — shape detected automatically, check edges".

### 5.7 Path editing (vectors)
- Enter path mode: hide rest of object's controls; show point handles (white squares), segment lines.
- Click point → select (accent fill); drag to move; `Shift` box-selects multiple points.
- `⌫` deletes selected points; double-click segment adds point.
- Bezier handles appear for curves (accent circles, 1px lines).
- Escape drains to object mode; `Edit path` toggle returns.

### 5.8 Save, version, share, export
- **Save (Ctrl+S):** autosaves (debounced 800ms after change) when authed; status bar shows `Saving…` → `Saved. Just now`. Ctrl+S forces.
- **Versions:** `Version history` opens a right drawer: list rows (time · "Snapshot N" · size), `[Restore]` (warning modal: "This replaces the current design"), `[Diff]` (thumb-only compare).
- **Share:** modal → `[Copy link]` with permission toggle `View / Edit` segmented; toggle off revokes with confirm; shows access count.
- **Export (toolbar `Export ▾`):** menu: PNG \@1x, PNG \@2x, JPG (quality 85), SVG, PDF (disabled → tooltip "Coming in v0.5"). Choose → modal with format options (transparent bg toggle for PNG; scale for JPG), `[Export]` → progress 300ms → `[Download]` link (signed URL). Exports are server-rendered (§3.2 v0.1–v0.5). Success toast.

### 5.9 Undo/redo & shortcuts
- Undo/redo operate on scene graph snapshots. Depth: 100 steps. `Ctrl+Z`/`Ctrl+Shift+Z`; toolbar buttons show disabled at ends.
- Shortcuts panel (toolbar `?`): full map — `V` select, `H` hand, `T` text, `R` rect, `O` ellipse, `Ctrl+D` duplicate, `Del` delete, `Ctrl+G/U` group/ungroup, `Space` pan, `+/-` zoom, `I` import.

---

## 6. Keyboard navigation & accessibility

- Every canvas control reachable via Tab; visible focus ring never removed.
- Panels/layers use native focus; arrow-key layer navigation (up/down) + `Enter` rename/select.
- Color inputs open with built-in picker + hex field; color vision: don't rely solely on color (always pair with text/icon).
- Canvas objects expose aria-labels `type + name`; live regions announce "Added circle", "Layer hidden", "Confidence 62%".
- High-contrast mode: bump borders to `border-strong` and text to 100% white.
- Drag-drop has keyboard fallbacks: `Import` menu → file picker accessible via keyboard.
- Reduced motion: all 150–300ms transitions become instant; progress pulse becomes static.

---

## 7. States & error handling

| State | Spec |
|-------|------|
| Empty scene | Hints: "Nothing detected — import a richer design or add layers manually." |
| Loading editor | 300ms skeleton: toolbar + panel placeholders + canvas checkerboard shimmer |
| Network drop (SSE) | Auto-reconnect (exp backoff); banner "Reconnecting…" if editor in draft – no data loss cues |
| Job failed | Shown at §4.3 with retry |
| Save failed | Toast error + `Saving…` → `Save failed · Retry` in status bar |
| Export failed | Modal "Export failed — [Retry] [Report]" |
| Auth required mid-flow | Centered card "Sign in to save this project" with `[Continue to editor as guest]` (draft retained) |
| Share token expired/invalid | Dedicated 404-style page "This design link is no longer available." |
| Delete project/template | Confirm modal; destructive action last, no undo toast after confirm |
| Access denied | 403 page with "Back to projects" |

---

## 8. Phasing & deferred details

### 8.1 Phased delivery (matches `roadmap.md`)
- **v0.1/v0.2 (MVP):** shell + upload/progress (§4) + editor core (§5.1–5.5) + text/shape/image properties + confidence chips (§5.6) + export PNG/JPG/SVG + `.p2l` save/load (draft mode). Settings and Templates gated behind "Coming soon" tooltips.
- **v0.3:** auth screens (§3.2), Projects dashboard (§3.3), version drawer (§5.8), save-on-account.
- **v0.4:** vector path editing (§5.7), segment confidence + "Approximate" badges, Confidence panel detail, "Show low-confidence" toggle, smart grouping hints.
- **v0.5:** Templates gallery (§3.4), share links (§3.6/§5.8), batch flow (§4.5), PDF export.

### 8.2 Explicitly deferred (post-v0.5)
- Light theme, dynamic dashboard layouts/custom canvas sizes (v0.2 fixed ratios only), CMYK/print prep, live collaboration UI, des
ign-system components/auto-layout, native touch tooling.

---

## 9. Definition of Done (frontend)

- [ ] Implements the section(s) of this spec for the current milestone.
- [ ] Uses the tokens in §1.3/§1.4, no ad-hoc colors/type.
- [ ] Keyboard-navigable with visible focus (Tab-through verified).
- [ ] All states in §7 for the touched surfaces implemented (incl. empty/error/loading).
- [ ] Confidence data shown wherever schema provides it; never dropped.
- [ ] Editor behaviors wired to SceneGraphSchema via the shared contract (no parallel local schema).
- [ ] Lint + typecheck pass; e2e coverage for canvas behaviors updated.