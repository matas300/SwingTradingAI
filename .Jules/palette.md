## 2024-05-18 - Missing Keyboard Focus States
**Learning:** The application lacks visual focus indicators for interactive elements (buttons, inputs, links), which severely hinders keyboard accessibility. Relying on default browser focus rings is insufficient or they are sometimes hidden.
**Action:** Always explicitly define `:focus-visible` styles for component classes using theme-aware design tokens to ensure consistent, accessible navigation across all interactive states.
