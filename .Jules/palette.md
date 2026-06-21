## 2024-06-04 - Lack of Explicit Focus Indicators
**Learning:** The application lacked explicit `:focus-visible` styles for interactive elements, relying on browser defaults which are often insufficient for good keyboard accessibility.
**Action:** Append explicitly defined `:focus-visible` pseudo-class rules directly to existing interactive component classes (e.g., `.primary-button:focus-visible`, `input:focus-visible`) and reference existing design tokens like `var(--accent)` for the outline.
