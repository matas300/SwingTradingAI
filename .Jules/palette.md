## 2024-05-24 - Explicit Focus States Needed
**Learning:** This app's custom CSS strips default browser outlines but fails to replace them with custom focus indicators, making keyboard navigation nearly impossible for users who rely on it.
**Action:** Added global `:focus-visible` styles utilizing the existing `var(--accent)` design token to ensure all interactive elements receive clear, accessible focus indicators without disrupting mouse/touch user experience.
