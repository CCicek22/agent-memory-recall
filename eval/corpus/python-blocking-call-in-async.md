---
title: A blocking call inside async code stalls the event loop
---

# A blocking call inside async code stalls the event loop

One synchronous file read or HTTP request inside a coroutine blocks every other task on the loop. Use an async client, or run the blocking function in a thread with asyncio.to_thread. Watch for this in code review.
