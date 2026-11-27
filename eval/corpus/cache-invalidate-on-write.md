---
title: Invalidate cache entries on write
---

# Invalidate cache entries on write

A cache with a time-to-live alone can show a changed price for minutes after the update. Delete or rewrite the affected keys in the same code path that writes the source record, and keep the TTL as a safety net.
