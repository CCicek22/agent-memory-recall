---
title: Paginate with a cursor, not an offset
---

# Paginate with a cursor, not an offset

Offset paging skips or repeats rows when records are inserted between pages. A cursor that points at the last seen sort key stays stable. Return an opaque next-cursor token and sort by a unique column.
