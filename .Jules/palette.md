## 2024-11-20 - SPA Navigation ARIA Current State
**Learning:** In SPAs (Single Page Applications) where navigation links toggle an "active" class (like `.is-active`), screen readers may not be aware of the state change unless explicit ARIA attributes are updated.
**Action:** When toggling class states for active navigation links, explicitly set `aria-current="page"` on the active link and remove it from inactive ones to ensure screen readers announce the current page correctly.
