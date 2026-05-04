## 2024-06-25 - Prevent Accidental Data Loss with Popovers
**Learning:** Destructive actions like clearing an entire plan should never be a single click away. Using `st.popover` for confirmation dialogs is an effective, non-intrusive way to ensure users truly intend to delete their data.
**Action:** Always wrap destructive actions in a confirmation popover using `st.popover`.

## 2024-06-25 - Improve Accessibility with Tooltips
**Learning:** Disabled buttons or icon-only buttons can be confusing to users and inaccessible to screen readers. Adding a `help` parameter to Streamlit buttons provides necessary context.
**Action:** Use the `help` parameter to provide tooltips for buttons, especially when they are disabled or lack clear text labels.
