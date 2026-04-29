## 2025-05-15 - UX Deletion Confirmation
**Learning:** Users can easily misclick small icons like trash bins. Implementing a two-step confirmation (popover + button) significantly reduces friction from accidental deletions in interactive lists.
**Action:** Use the pattern `with st.popover('🗑️'): st.button('Confirmar')` for list item deletions.
