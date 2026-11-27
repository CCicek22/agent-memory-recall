---
title: Store money in integer cents or Decimal
---

# Store money in integer cents or Decimal

Binary floats cannot represent most decimal amounts exactly, so sums drift by a cent. Store amounts as integer minor units or use decimal.Decimal with an explicit quantize step at the rounding boundary.
