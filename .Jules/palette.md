## 2024-05-18 - First entry
**Learning:** Initialize journal.
**Action:** Let's look for UX improvements.
## 2024-05-18 - Added keyboard focus states for accessibility
**Learning:** Found that this app's UI lacked explicit global focus indicators, rendering it inaccessible to keyboard-only navigation. The design system uses custom buttons (`.primary-button`, `.secondary-button`, etc.) and nav links without a default browser outline fallback or a custom `.focus-visible` ring.
**Action:** Always verify that custom interactive components define a `:focus-visible` state. Added explicit focus outlines to existing interactive classes using `var(--accent)` to maintain visual consistency while passing a11y checks.
