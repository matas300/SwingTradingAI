## 2026-06-03 - Added keyboard focus states
**Learning:** The application lacked explicit `:focus-visible` styles for interactive elements, which made keyboard navigation difficult. Standard components like buttons and inputs did not provide adequate visual feedback when focused.
**Action:** Append explicitly defined `:focus-visible` pseudo-class rules directly to existing component classes in `styles.css`, referencing existing design tokens like `var(--accent)` for the outline.
