## 2024-05-14 - Keyboard Accessibility: Focus Visible

**Learning:** The application's base CSS did not include explicit `:focus-visible` styles for interactive elements. This lack of focus indication makes keyboard navigation extremely difficult for users relying on it. Some browsers/CSS resets strip default outlines, making it essential to provide clear, custom focus indicators.
**Action:** Added a global `:focus-visible` rule targeting links, buttons, and form inputs. Used `var(--accent)` to match the existing design tokens and `outline-offset` to ensure the focus ring is clearly visible and detached slightly from the element itself. Always verify focus states when styling new interactive components.
