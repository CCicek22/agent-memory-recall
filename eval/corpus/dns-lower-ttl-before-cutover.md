---
title: Lower the DNS TTL before a cutover
---

# Lower the DNS TTL before a cutover

Resolvers cache records for the old TTL, so a change takes that long to reach every client. Lower the TTL a day or more before the move, make the switch, verify, and raise the TTL again once stable.
