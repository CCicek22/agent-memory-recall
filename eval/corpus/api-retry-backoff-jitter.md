---
title: Retry with exponential backoff and jitter
---

# Retry with exponential backoff and jitter

Immediate retries against a struggling service multiply the load that caused the failure. Wait twice as long after each failure, cap the wait, and add random jitter so many clients do not retry in lockstep. Retry only errors that are safe to repeat.
