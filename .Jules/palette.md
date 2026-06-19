## 2026-04-28 - Component-Scoped Keyboard Focus
**Learning:** Adding global `*:focus-visible` rules can cause unintended side effects across the app.
**Action:** Instead of global styles, append explicitly defined `:focus-visible` rules directly to existing component classes (e.g., `.primary-button:focus-visible`, `.search-field input:focus-visible`) referencing existing design tokens.
