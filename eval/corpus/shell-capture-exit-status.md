---
title: Capture an exit status right after the command
---

# Capture an exit status right after the command

The special variable holding the last exit status is overwritten by every command that runs, including the test in an if. Save it into a variable immediately after the command you care about, then branch on the saved value.
