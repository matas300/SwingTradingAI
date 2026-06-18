## 2026-05-03 - Component-specific Focus Styles
**Learning:** Applying a global `*:focus-visible` rule in pure CSS projects can lead to unintended visual regressions or conflicts with specific component designs.
**Action:** Always append explicitly defined `:focus-visible` pseudo-class rules directly to existing component classes (e.g., `.primary-button:focus-visible`, `input:focus-visible`) and reference existing design tokens like `var(--accent)` for the outline to ensure robust and accessible keyboard navigation without unintended side effects.
