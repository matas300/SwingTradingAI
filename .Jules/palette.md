## 2024-05-17 - Missing keyboard focus indicators

**Learning:** The application lacks default keyboard focus indicators for interactive elements. Relying only on browser defaults or having none significantly harms keyboard accessibility. Furthermore, using a global `*:focus-visible` reset may not work well with all UI components.

**Action:** Explicitly append `:focus-visible` pseudo-class rules directly to existing interactive component classes (e.g., buttons, inputs, links) referencing existing design tokens like `var(--accent)` for the outline instead of introducing custom global CSS.