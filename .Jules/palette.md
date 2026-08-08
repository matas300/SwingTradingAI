## 2024-05-10 - Missing Focus Indicators
**Learning:** The application's styles.css completely lacks `:focus` or `:focus-visible` states for interactive elements, which is a major accessibility issue for keyboard users.
**Action:** Add explicit `:focus-visible` rules for buttons, links, and form inputs using existing design tokens (e.g., `var(--accent)` for outline color).
