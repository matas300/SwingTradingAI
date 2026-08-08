## 2026-06-20 - Missing Focus Indicators on Interactive Components
**Learning:** Custom interactive components (like buttons, navigation links, and inputs) lacked native `:focus-visible` states, making keyboard navigation difficult or invisible.
**Action:** Implemented explicit `:focus-visible` rules for all custom interactive classes (`.primary-button`, `.nav-stack a`, etc.) using `outline: 2px solid var(--accent); outline-offset: 2px;` to ensure accessibility without affecting mouse users.
