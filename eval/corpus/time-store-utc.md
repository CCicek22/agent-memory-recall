---
title: Store timestamps in UTC and convert at the edge
---

# Store timestamps in UTC and convert at the edge

Local-time timestamps break when users or servers change zone or daylight saving time. Store UTC with the offset, convert to the user's zone only when displaying, and bucket reports by the zone the report is about.
