## 2026-04-24 - Added keyboard focus states
**Learning:** The base CSS configuration lacks default outlines for interactive elements, which is a critical accessibility issue for keyboard navigation. We must explicitly define `:focus-visible` styles referencing existing design tokens (e.g., `var(--accent)`) to ensure accessibility.
**Action:** Always verify keyboard navigation and focus indicators when creating or modifying interactive elements.
