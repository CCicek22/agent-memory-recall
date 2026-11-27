---
title: Cap the connection pool per instance
---

# Cap the connection pool per instance

Each app instance opens its own pool, so adding instances multiplies connections against the database limit. Set the pool size from the database's max connections divided by the instance count, and use a pooler in front when the count grows.
