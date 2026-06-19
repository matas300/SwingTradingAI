## 2026-04-10 - Explicit Focus Visible Styles
**Learning:** The project relies on explicit `:focus-visible` properties referencing existing design tokens (e.g. `var(--accent)`) for keyboard accessibility, because standard styling resets omit clear outline defaults.
**Action:** When adding or modifying interactive UI components, ensure that `:focus-visible` states are explicitly applied so that users navigating via keyboard have a clear visual indicator of the focused element.
