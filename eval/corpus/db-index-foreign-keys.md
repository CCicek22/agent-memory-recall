---
title: Index the foreign key columns
---

# Index the foreign key columns

Postgres does not index referencing columns automatically. Deleting a parent row then scans the whole child table to check for references. Add an index on each foreign key column that is used in joins or deletes.
