## 2026-04-11 - Base CSS Required Explicit Focus Visible Indicator
**Learning:** The base CSS in this design system does not define proper keyboard focus states natively. Keyboard accessibility requires manually specifying `:focus-visible` pseudo-class rules using existing design tokens (e.g. `var(--accent)`).
**Action:** When adding new interactive elements (like custom buttons or input wrappers), ensure `:focus-visible` is styled with existing tokens to maintain a11y standards.
