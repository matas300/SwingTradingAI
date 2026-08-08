## 2024-05-24 - Interactive Element Focus Styles
**Learning:** Custom interactive elements (e.g., `<button>` reset styles, `<a>` tag custom borders) often lose default browser focus outlines, hindering keyboard accessibility for power users and screen readers.
**Action:** When creating or resetting interactive components without a global `*:focus-visible` rule, ensure `:focus-visible` is explicitly defined on each component class with an outline that contrasts well against the background (e.g., using `var(--accent)`).
