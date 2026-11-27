---
title: Every outbound call needs a timeout
---

# Every outbound call needs a timeout

A default of no timeout lets one slow dependency hold a worker forever. Set connect and read timeouts on every HTTP and database client, and size the worker pool so a slow dependency cannot exhaust it.
