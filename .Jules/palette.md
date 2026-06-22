## 2024-05-18 - Missing focus states
**Learning:** The application lacks focus-visible states for critical interactive elements like buttons, links, inputs, selects, and textareas, making keyboard navigation difficult and failing WCAG 2.1 Focus Visible standards.
**Action:** Add outline/ring styles using existing design tokens (e.g., `var(--accent)`) specifically with the `:focus-visible` pseudo-class across interactive component classes.
