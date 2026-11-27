---
title: Send an idempotency key with unsafe retries
---

# Send an idempotency key with unsafe retries

A timed-out POST may or may not have succeeded. Attach a client-generated idempotency key so the server returns the original result when you resend the same request. Store the key with the request before sending it.
