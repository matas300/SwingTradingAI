## 2026-06-05 - Global Accessibility Focus Indicators
**Learning:** Adding `:focus-visible` pseudo-class rules globally across interactive components ensures accessibility without resorting to generic `*:focus` rules that could unintentionally impact visual design. Appending explicitly to predefined utility classes maintains specificity and consistency with the design tokens.
**Action:** Always append `:focus-visible` states explicitly to standard interactive classes rather than relying on wildcard rules to ensure robust keyboard accessibility.
