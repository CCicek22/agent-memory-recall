---
title: Alert on the absence of a success signal
---

# Alert on the absence of a success signal

A job that stops running raises no error, so an error alert never fires. Have each scheduled job record a heartbeat on success, and alert when the last heartbeat is older than the expected interval plus a margin.
