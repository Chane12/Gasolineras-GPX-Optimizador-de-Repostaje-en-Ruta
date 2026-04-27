## 2024-04-27 - Streamlit Destructive Action Popovers
**Learning:** Destructive actions (like clearing a route plan) in Streamlit should not rely on a single button click, as misclicks are common on mobile interfaces. The `st.popover` component is an excellent, native way to build confirmation dialogs without resorting to modal workarounds.
**Action:** Use `st.popover` to wrap any destructive buttons in the future to enforce a two-step confirmation process.

## 2024-04-27 - Playwright Frontend Testing
**Learning:** During frontend verification, adding the `playwright` dependency temporarily modified the `pyproject.toml` and lock files.
**Action:** Always clean up temporary dependencies (`uv remove <package>`) and script files used for verification before requesting a code review or submitting a PR.
