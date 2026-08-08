## 2026-04-30 - Added Explicit Focus States

**Learning:** Custom UI components in this app (like `.primary-button`, `.nav-stack a`, `.list-row`) did not have built-in explicit focus indicators, which made keyboard navigation inaccessible. The use of a global `*:focus-visible` was avoided per requirements, so component-level classes needed targeted pseudo-selectors.
**Action:** Always append `.class:focus-visible` to interactive components when building or modifying custom UI, and reference existing design tokens (e.g. `var(--accent)`) with an `outline-offset` to keep it accessible and matching the design language.
