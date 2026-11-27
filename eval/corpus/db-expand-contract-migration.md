---
title: Rename columns with expand and contract
---

# Rename columns with expand and contract

During a rolling deploy the old and new app versions run at the same time. First add the new column and write to both, then backfill and switch reads, and only drop the old column in a later release. Never rename in one step.
