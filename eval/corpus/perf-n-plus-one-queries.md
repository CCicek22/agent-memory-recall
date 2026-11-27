---
title: Fix N+1 queries with a batched load
---

# Fix N+1 queries with a batched load

Loading a list and then one related record per row issues hundreds of tiny queries. Load the related rows in one query with an IN clause or a join, then attach them in memory. Count queries per request in tests.
