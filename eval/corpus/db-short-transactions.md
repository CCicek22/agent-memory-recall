---
title: Keep database transactions short
---

# Keep database transactions short

A transaction that waits on a network call keeps its row locks while the call is pending. Fetch and compute outside the transaction, then open it only for the writes. Set a statement timeout so a stuck lock fails fast.
