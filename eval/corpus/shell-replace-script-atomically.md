---
title: Replace a running script atomically
---

# Replace a running script atomically

Bash reads a script as it executes, so editing it in place can change the code under a running job. Write the new version to a temporary file in the same directory and move it over the old name. The rename is atomic on one filesystem.
