## 2026-05-11 - Missing keyboard focus states

**Learning:** This design system lacked visual keyboard focus indicators. This severely hindered keyboard accessibility because users couldn't tell which interactive element had focus when tabbing through the app. A global `*:focus-visible` rule was not desired.
**Action:** Append explicit `:focus-visible` pseudo-class rules directly to existing component classes (e.g., `.primary-button:focus-visible`, `.nav-stack a:focus-visible`, form elements) and reference existing design tokens like `var(--accent)` for the outline. All new interactive components added to the system must include explicitly defined `:focus-visible` states.
