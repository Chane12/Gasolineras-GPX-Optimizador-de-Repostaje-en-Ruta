## 2024-05-24 - Confirmación para acciones destructivas en UI
**Learning:** Wrapped destructive action buttons like deleting rows or clearing data with `st.popover` effectively creates a minimal interruption confirmation dialog, improving UX by preventing accidental data loss without requiring heavy modals.
**Action:** Use `st.popover` for any button that deletes user data or clears states (like `mis_paradas`), adding a final "Confirmar" button inside the popover.
