## 2024-05-24 - Accessibility Keyboard Focus
**Learning:** This application's custom UI elements lack `:focus-visible` outlines for keyboard navigation, making the interface completely inaccessible for users tabbing through elements.
**Action:** Always add `:focus-visible` pseudo-class styles to interactive elements like buttons, inputs, and links to ensure keyboard navigation focus is clear, using existing design tokens like `var(--accent)`.
