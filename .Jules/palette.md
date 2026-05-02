## 2026-05-02 - Prevent Accidental Data Loss with Popovers
**Learning:** Wrapping destructive actions (e.g. deleting or clearing data) directly in Streamlit buttons without confirmation dialogues allows for accidental data loss. Using `st.popover` as a lightweight confirmation container before executing the destructive action provides a robust UX safety net while preserving the declarative UI structure.
**Action:** Always wrap destructive or state-resetting actions in `st.popover` with a clear secondary confirmation button instead of binding them directly to single-click top-level buttons.
