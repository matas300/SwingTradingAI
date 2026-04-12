## 2026-04-12 - Focus Outline Accessibility
**Learning:** The default base CSS configuration strips the default browser focus outline, making it extremely difficult to identify active keyboard navigation elements.
**Action:** Add explicit `:focus-visible` properties on all interactive inputs relying on standard app design tokens (like `--accent`) to ensure WCAG compliant focus indications without affecting pointer users.
