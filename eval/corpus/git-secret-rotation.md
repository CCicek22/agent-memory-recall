---
title: Rotate a leaked secret, do not just delete the commit
---

# Rotate a leaked secret, do not just delete the commit

Once a secret reaches a remote it should be treated as public, because clones and caches keep it. Revoke or rotate the credential first, then clean the history if you still need to. Check the provider's audit log for use.
