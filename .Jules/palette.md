## 2024-04-21 - Keyboard Navigation and Focus Styles
**Learning:** The base CSS styling stripped default focus outlines across the application. To maintain keyboard accessibility, `:focus-visible` properties must be explicitly defined for all interactive elements (links, buttons, inputs, selects, textareas).
**Action:** When creating new interactive components or modifying global styles, ensure explicit `:focus-visible` styles are included, preferably referencing existing design tokens like `var(--accent)` for visual consistency.
