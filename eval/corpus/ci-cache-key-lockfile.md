---
title: CI cache key must include the lockfile hash
---

# CI cache key must include the lockfile hash

Dependency caches keyed only by the branch name keep serving old packages after an upgrade. Key the cache on a hash of the lockfile so any change to resolved versions produces a fresh cache. Keep a restore-keys fallback for speed.
