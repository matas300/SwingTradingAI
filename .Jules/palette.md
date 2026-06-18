## 2024-05-24 - Focus Visible States

**Learning:** Base CSS often removes default focus outlines, leaving keyboard users without visual indicators for navigation. It's critical to add explicit `:focus-visible` styles to all interactive elements (buttons, links, inputs, selects, textareas).
**Action:** Always ensure `:focus-visible` is defined using a clear design token (like `var(--accent)`) to maintain keyboard accessibility without relying on browser defaults which may be stripped.
