## Mandatory validation results — local source snapshot

| Check | Result | Exact observed value |
|---|---|---|
| Total orders ≈99,441 | PASS | 99,441 |
| Late vs on-time low-review share ≈62% / 9% | PASS | 3,983/6,381 = 62.4197%; 8,289/89,443 = 9.2674% |
| Delivered average rating ≈4.16 | PASS | 4.155908256115, on 95,832 reviewed delivered orders |
| Revenue = source price + freight | PASS | R$15,843,553.24; aggregate difference < R$0.005 |
| Unique dimension keys and no orphan fact keys | PASS | Customer/product/seller keys unique after stated person consolidation; zero source order/customer and item/order/product/seller orphans |

Tolerance was defined as ±2 percentage points for approximate review shares and ±0.02 stars for rating. No values were changed to fit benchmarks. There are 96,478 delivered orders, 96,470 with usable delivery dates, and 6,534 late orders (6.7731%). There are 6,381 reviewed late orders versus 89,443 reviewed on-time orders. Eight reviewed delivered orders with unknown delay contribute to overall rating but not either delivery cohort.

Python validates source keys and equivalent transformations; only a successful Desktop refresh followed by engine queries can prove parity with the loaded Power Query model. `validation/schema_results.json` records PBIR schema validation separately. `validate_model.ps1` uses installed Microsoft TOM libraries to parse the BIM.

