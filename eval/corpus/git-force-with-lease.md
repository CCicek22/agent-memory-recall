---
title: Use force-with-lease when rewriting a shared branch
---

# Use force-with-lease when rewriting a shared branch

A plain force push can silently delete a teammate's commits. force-with-lease refuses the push if the remote moved since your last fetch. Use it only on your own feature branches, never on the default branch.
