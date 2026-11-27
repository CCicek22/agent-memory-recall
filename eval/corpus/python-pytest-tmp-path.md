---
title: Use tmp_path for test files
---

# Use tmp_path for test files

Tests that write to a fixed path collide when run in parallel or in a second session. The tmp_path fixture gives each test a unique directory that pytest cleans up. Avoid writing into the repository from tests.
