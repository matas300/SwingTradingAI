## 2024-05-18 - Missing keyboard focus indicators
**Learning:** Default CSS resets and configurations often strip browser default focus outlines, making keyboard navigation nearly impossible for users relying on tab targeting.
**Action:** Always explicitly define `:focus-visible` styles on interactive elements (buttons, links, inputs, selects, textareas) referencing existing design system tokens (e.g., `var(--accent)`) to ensure accessible keyboard navigation.
