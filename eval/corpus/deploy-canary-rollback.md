---
title: Decide on rollback criteria before the canary
---

# Decide on rollback criteria before the canary

Shipping to a small slice first only helps if you know what result means stop. Write the error rate, latency, and business metric thresholds before the rollout, watch them for a fixed window, and roll back automatically when one is crossed.
