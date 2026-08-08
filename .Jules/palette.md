## 2024-05-24 - Keyboard Accessibility in Base Styles
**Learning:** The application base styles do not include a global `:focus-visible` ring. While the design is modern, default browser focus rings may be stripped or lack sufficient contrast against custom themes.
**Action:** Implement a generic `:focus-visible` outline using the existing design token `var(--accent)` to ensure keyboard navigation is visible across all interactive elements without affecting mouse users.
