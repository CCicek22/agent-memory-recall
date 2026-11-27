---
title: Quote variable expansions in shell scripts
---

# Quote variable expansions in shell scripts

Unquoted variables split on spaces and expand glob characters, so a file named with a space becomes two arguments. Quote every expansion, such as "$file", and iterate with while read or find -print0 instead of word splitting.
