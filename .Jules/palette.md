## 2026-06-10 - Missing Focus-Visible Styles for Better Keyboard Accessibility
**Learning:** Found that the app relied on default browser focus rings which can be inconsistent or missing, making keyboard navigation (like tabbing through `a`, `button`, `input` tags) confusing for users. Appending `:focus-visible` pseudo-class explicit focus outlines helps maintain keyboard accessibility without disrupting visual appeal for mouse users.
**Action:** Applied `:focus-visible` explicitly to existing component classes to show an explicit 2px solid outline using the existing `var(--accent)` color.
