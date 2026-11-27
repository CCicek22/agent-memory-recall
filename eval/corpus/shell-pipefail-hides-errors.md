---
title: Set pipefail or a pipeline can hide a failure
---

# Set pipefail or a pipeline can hide a failure

Without pipefail, a pipeline's exit status is the last command's status. A crash in the first stage passes silently. Put set -euo pipefail at the top of scripts and test the failure path once on purpose.
