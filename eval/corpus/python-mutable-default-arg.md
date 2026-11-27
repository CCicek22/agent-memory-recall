---
title: Never use a mutable default argument
---

# Never use a mutable default argument

A default list or dict is created once when the function is defined, so every call that relies on it shares the same object. Default to None and create the list inside the function body.
