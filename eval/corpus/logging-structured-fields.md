---
title: Log events as structured fields
---

# Log events as structured fields

Free-text messages with values pasted in are hard to filter. Emit a fixed event name and separate key-value fields such as user_id and duration_ms. A query can then count or group by a field without regex.
