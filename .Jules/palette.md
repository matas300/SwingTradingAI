## 2024-06-08 - Keyboard Focus States for Accessibility
**Learning:** The application lacked explicit focus indicators for keyboard navigation across its interactive components (buttons, links, inputs). Relying on browser defaults or having none at all makes the app difficult or impossible to use for keyboard-only users.
**Action:** Always append explicitly defined `:focus-visible` pseudo-class rules directly to existing component classes referencing existing design tokens like `var(--accent)` for the outline instead of adding custom global CSS.
