## 2026-05-22 - Missing focus-visible states
**Learning:** The application lacked visual indicators for keyboard focus across navigation links and various button types, making keyboard navigation difficult or impossible for users relying on it.
**Action:** Always append `:focus-visible` pseudo-class rules (e.g., `outline: 2px solid var(--accent); outline-offset: 2px;`) explicitly to existing component classes to ensure accessibility without breaking pointer device interactions.
