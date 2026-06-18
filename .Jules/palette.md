## 2024-06-14 - Keyboard focus indicators missing from component classes
**Learning:** In this vanilla HTML/CSS app, base interactive components (like `.primary-button`, `.secondary-button`, `.search-field input`, etc.) lack default keyboard focus indicators because no global `*:focus-visible` rule is defined.
**Action:** When adding or updating interactive elements, always explicitly apply a `:focus-visible` pseudo-class (e.g. `.my-button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }`) to ensure keyboard accessibility.
