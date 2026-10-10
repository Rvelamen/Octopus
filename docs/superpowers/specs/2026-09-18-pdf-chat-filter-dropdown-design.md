# PDF Chat Annotation Filter Dropdown — Design Spec

**Date:** 2026-09-18
**Status:** Approved (awaiting implementation plan)
**Owner:** TBD

## Context & Problem

The PDF chat drawer in `frontend/src/pages/PdfViewerWindow.jsx` lets the user
scope chat sessions to a single annotation or to all annotations. The current
implementation uses a native HTML `<select>` element
(`PdfViewerWindow.jsx:879-908`) and is the only chrome in the drawer that does
not match the custom dark-theme styling of the surrounding session list. The
goal of this change is to replace that native control with a custom dropdown
that is visually consistent with `.pdfv-chat-session`, exposes richer
per-annotation metadata (color bar, page badge, longer text preview), and
feels like a first-class part of the chat drawer rather than a default
browser widget.

## Goals

1. Replace the native `<select>` with a custom dropdown whose trigger and
   list items reuse the existing `.pdfv-chat-session` card style.
2. Each list item shows: a 4px color bar (from `annotation.color`), a page
   badge (`P<n>·`), and a 50-character text preview (longer than today's 40
   characters).
3. Selected state uses the existing `.pdfv-chat-session-active` highlight
   plus a `Check` icon on the right.
4. The dropdown panel floats above the messages area (absolute positioning,
   `z-index: 30`) so it does not reflow the chat layout.
5. Provide an empty state when `annotations` is empty: a single
   "All annotations" trigger plus a "no annotations yet" placeholder.
6. Keep functional behavior identical: the chosen value drives
   `useAnnotationChat`'s `annotationId` parameter via
   `chatAnnotationFilter` state. Selecting a different filter reloads the
   session list through the existing hook.
7. **Behavior change:** selecting a new filter does **not** clear the current
   `chatSessionId`. The user explicitly requested preserving the current
   session across filter changes; if the existing session is still in scope
   for the new filter it remains selected, otherwise the hook will surface an
   empty message list and the user can pick another session.

## Non-Goals

- No new backend APIs or schema changes.
- No change to `useAnnotationChat` or any handler/service code.
- No change to chat message rendering, input box, or session list behavior.
- No change to the i18n key `annotation.chatForAnnotation` (existing template
  `{{preview}}`); we only add one new key (`annotation.filterEmpty`).
- No light-mode support — the drawer is already dark-theme only.

## UX / Visual Design

### Trigger (button)

- Reuses `.pdfv-chat-session` class so it visually matches session cards.
- Left edge: a 4px vertical color bar in the trigger's own color.
  - For "All annotations": use `#4a9eff` (the chat-active blue) so the
    trigger never looks broken even when nothing is selected.
  - For a specific annotation: use `annot.color` (fallback `#1890ff`).
- Center: trigger label.
  - "All annotations": `t('annotation.chatAllAnnotations')`.
  - For an annotation: `t('annotation.chatForAnnotation', { preview: … })`,
    where the preview is `annot.text.slice(0, 50)` plus an ellipsis when
    truncated. (The preview is the same shape as today but longer.)
- Right: `ChevronDown` (12px) from `lucide-react`. Rotates 180° when the
  panel is open (CSS `transform`).

### Panel

- `position: absolute; top: calc(100% + 4px); left: 10px; right: 10px;`
- `z-index: 30` (above `.pdfv-chat-context`, `.pdfv-chat-passages`, and
  `.pdfv-chat-messages`).
- `background: #252525; border: 1px solid #333; border-radius: 6px;`
- `max-height: 280px; overflow-y: auto;` (its own scrollbar; mirrors
  `.pdfv-chat-sessions`).
- `padding: 4px 0;` (gives the items room to breathe and match session card
  list density).

### List item

- Reuses `.pdfv-chat-session` class so hover/active styles come for free.
- 4px vertical color bar at the left (`background: annot.color || #1890ff`).
- A small page badge rendered as plain text inside the title area:
  - Format: `P3 · {preview}` (the en-dash is the U+00B7 middle dot to match
    the existing dot used elsewhere in the file).
  - Badge color: `var(--accent)` (currently `#4a9eff`); font-size 10px;
    font-weight 600; `margin-right: 6px`.
  - If `annot.page` is missing/falsy, the badge is omitted (don't render an
    empty `P0`).
- Title text: existing 50-char preview.
- Right side: when the item equals `chatAnnotationFilter` (or `__all__`
  maps to `null`), show `<Check size={12} />` icon. For other items: render
  an empty placeholder span with the same width so the title text does not
  jump when selection changes.
- Same `.pdfv-chat-session-delete`-style delete button is **not** rendered on
  filter items (deletes only exist for chat sessions, not annotations).

### Empty state

- When `annotations.length === 0`:
  - The trigger still renders "All annotations" (the only valid choice).
  - Inside the panel, render a single centered placeholder:
    `t('annotation.filterEmpty')` at `color: #666; font-size: 11px;
    padding: 20px 12px; text-align: center`.

## Interaction

| Event | Result |
|---|---|
| Click trigger | Toggle `isFilterOpen`. |
| Click an item | `setChatAnnotationFilter(value)` (number or `null`), then `setIsFilterOpen(false)`. The current `chatSessionId` is **preserved** (do not call `setChatSessionId(null)`). |
| Click outside the trigger or panel | `setIsFilterOpen(false)`. |
| Press `Esc` while panel is open | `setIsFilterOpen(false)`. |
| Press `Enter` / `Space` on trigger (keyboard) | Same as click. |
| Hover an item | Existing `.pdfv-chat-session:hover` background (`#2a2a2a`). |

The click-outside detection is implemented with a single `useEffect` that
registers a `mousedown` listener on `document` while `isFilterOpen` is true
and removes it on cleanup. The handler compares `e.target` against
`filterButtonRef.current` and `filterPanelRef.current` (using
`Node.contains`).

## State & Data Flow

- New local state in the `PdfViewerWindow` component:
  - `const [isFilterOpen, setIsFilterOpen] = useState(false);`
  - `const filterButtonRef = useRef(null);`
  - `const filterPanelRef = useRef(null);`
- No changes to existing state. `chatAnnotationFilter` semantics are
  preserved; only the surrounding UI changes.

## i18n

Add a single new key to both locales:

- `frontend/src/i18n/locales/zh/translation.json`
  - `annotation.filterEmpty: "暂无批注，先在 PDF 里选中文字添加吧"`
- `frontend/src/i18n/locales/en/translation.json`
  - `annotation.filterEmpty: "No annotations yet — highlight text in the PDF to create one."`

Place the new key immediately after `chatForAnnotation` for grouping.

## Files Touched

| File | Change |
|---|---|
| `frontend/src/pages/PdfViewerWindow.jsx` | Replace the `<select>` block at lines 879-908 with the new custom dropdown component; add `useRef` import (already present); add `ChevronDown` and `Check` to the existing `lucide-react` import block. |
| `frontend/src/pages/PdfViewerWindow.css` | Add styles for `.pdfv-chat-filter-trigger`, `.pdfv-chat-filter-color-bar`, `.pdfv-chat-filter-chevron`, `.pdfv-chat-filter-panel`, `.pdfv-chat-filter-empty`, `.pdfv-chat-filter-page-badge`, `.pdfv-chat-filter-check`. |
| `frontend/src/i18n/locales/zh/translation.json` | Add `annotation.filterEmpty`. |
| `frontend/src/i18n/locales/en/translation.json` | Add `annotation.filterEmpty`. |

No backend or hook changes.

## Edge Cases

- `annotations` is `undefined` or `null`: treat as `[]` (mirrors today's
  behavior, which simply renders no `<option>` after "All annotations").
- `annotation.id` is missing or non-numeric: filter it out of the panel
  (mirrors today's `.filter(a => typeof a.id === 'number')`).
- `annotation.color` is missing: fall back to `#1890ff` (same default the
  current code uses elsewhere).
- `annotation.page` is missing/falsy: omit the `P<n>·` badge entirely.
- `annotation.text` is missing: preview is an empty string. Today the code
  already calls `(a.text || '').slice(...)` — preserve that.
- Filter changes while a streaming response is in flight: leave streaming
  state alone; the hook will reload sessions/messages when `annotationId`
  changes.

## Acceptance Criteria

1. The PDF chat drawer no longer contains any native `<select>` element.
2. The new dropdown trigger visually matches `.pdfv-chat-session` cards in
   the same drawer (same height, padding, font size, color).
3. Each annotation row in the panel shows the color bar, the `P<n>·` badge
   when `annot.page` is truthy, and the 50-char preview.
4. The currently-selected item shows `.pdfv-chat-session-active` background
   plus a `Check` icon on the right.
5. Clicking outside the panel or pressing `Esc` closes the panel.
6. When `annotations` is empty, the panel shows the localized
   `annotation.filterEmpty` placeholder.
7. The "All annotations" trigger works as it did before — selecting it sets
   `chatAnnotationFilter` to `null`, and the chat session list reloads.
8. Selecting a different annotation preserves the current `chatSessionId`
   (no automatic `setChatSessionId(null)`).
9. No new console errors or warnings during normal interaction.
10. Visual appearance is consistent in both dark theme contexts (no light
    mode expected, no regressions to other elements).

## Out of Scope / Future Work

- Light-mode theming of the chat drawer.
- Keyboard arrow-key navigation through the panel (mouse/touch and Tab are
  sufficient for now; can be added later without changing the public API).
- Migrating other native `<select>` elements in the codebase (this PR is
  scoped strictly to the PDF chat filter).
