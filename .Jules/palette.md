## 2024-05-02 - Component-Specific Focus Indicators
**Learning:** Adding global `*:focus-visible` styles can cause unintended side effects and break strict component boundaries or memory guidelines for UX enhancements in this project.
**Action:** Always append `:focus-visible` explicitly to existing, individual interactive component classes (e.g., `.nav-stack a:focus-visible`, `.primary-button:focus-visible`) and use standard design tokens like `var(--accent)` for the outline.
