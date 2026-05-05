## 2026-05-05 - Add explicit focus indicators for keyboard navigation
**Learning:** Found that this application has no keyboard focus indicators on interactive elements. The negative boundaries restrict the addition of custom global CSS or standard resets like `*:focus-visible`.
**Action:** Append explicitly defined `:focus-visible` pseudo-class rules directly to existing component classes in `static/styles.css` (e.g., `.primary-button:focus-visible`) and reference existing design tokens like `var(--accent)` for the outline.
