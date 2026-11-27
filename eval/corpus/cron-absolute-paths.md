---
title: Cron jobs need absolute paths and an explicit environment
---

# Cron jobs need absolute paths and an explicit environment

Cron runs with a minimal PATH and no interactive profile, so commands that work in your terminal fail silently. Use absolute paths to binaries, set PATH at the top of the crontab, and redirect output to a log you check.
