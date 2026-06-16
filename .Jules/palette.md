## 2026-06-16 - Add Focus Visible Styles for Interactive Elements
**Learning:** The app's custom UI components (like `.primary-button`, `.nav-stack a`, and icon-only buttons) lack explicit focus rings when navigating via keyboard, making it difficult for users relying on keyboard navigation to track their current position.
**Action:** Apply `outline: 2px solid var(--accent); outline-offset: 2px;` with the `:focus-visible` pseudo-class to all interactive elements to ensure consistent, highly visible focus states without impacting mouse-users.
