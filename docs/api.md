# API response semantics

## Monetary amounts

Nexus represents money in API responses as integer cents. Fields with names such as
`amount_cents`, `price_cents`, `paid_amount_cents`, or purchase-history totals are
whole cent values, not decimal yuan strings or floating-point numbers.

For RMB amounts, clients should format these integer cent values consistently as
Chinese yuan by dividing by 100 and rendering exactly two fractional digits with a
leading `¥` symbol. For example:

| Response value | UI display |
| --- | --- |
| `0` | `¥0.00` |
| `1` | `¥0.01` |
| `1999` | `¥19.99` |

Purchase history entries should display the stored cent amount for the completed
purchase without recalculating it from current product prices. This keeps historical
receipts stable even when prices change later.

Storing money as integer cents avoids floating-point money errors, such as binary
rounding artifacts from values like `0.1 + 0.2`, and keeps totals, comparisons, and
purchase history records exact.
