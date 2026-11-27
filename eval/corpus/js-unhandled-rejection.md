---
title: Handle promise rejections where they happen
---

# Handle promise rejections where they happen

A rejected promise with no handler can surface later as a crash far from the cause. Await async calls inside try blocks or attach a catch, and add a process-level handler that logs and exits cleanly so the failure is visible.
