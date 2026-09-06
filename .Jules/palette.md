## 2024-10-24 - explicit `:focus-visible` pseudo-class for Keyboard Accessibility
**Learning:** Depending purely on default browser focus rings without explicit `:focus-visible` pseudo-classes can lead to inconsistent and poor keyboard navigation UX.
**Action:** Always append explicitly defined `:focus-visible` pseudo-class rules directly to existing interactive component classes (e.g. `.primary-button:focus-visible`, `.nav-stack a:focus-visible`) and reference existing design tokens like `var(--accent)` for the outline offset.
