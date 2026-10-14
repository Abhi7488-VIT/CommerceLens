## Ten likely interview questions and short answers

1. **Why a star schema?** It separates descriptive dimensions from additive facts, gives predictable filtering, reduces duplication and makes business measures reusable.
2. **Why two fact grains?** Orders are one row per order; products and sellers occur at item grain. A single order fact cannot faithfully contain multiple product/seller keys without duplication.
3. **How do category filters affect order KPIs without bidirectional relationships?** Item filters produce distinct order IDs, then measures apply them to the order header with TREATAS and KEEPFILTERS. Unfiltered order totals still include orders without items.
4. **Explain the late-delivery measure.** CALCULATE restricts delivered orders to known dates and positive delay; DIVIDE uses eligible delivered orders as denominator and returns blank for an empty denominator.
5. **What is context transition here?** Repeat-customer logic iterates customer IDs. CALCULATE turns the current customer row into a filter before evaluating delivered orders, allowing a per-customer count.
6. **Why not join raw payments and items?** Both can have multiple rows per order, creating a fan-out join. Payments and items are aggregated independently before joining the order header.
7. **How does the what-if parameter work?** A disconnected numeric table supplies SELECTEDVALUE, default 0.5. Measures calculate alternative outcomes without changing historical data or relationships.
8. **How is projected rating estimated?** Shift a fraction of reviewed late orders from the observed late mean to the observed on-time mean, with review volume fixed. This is an assumption-driven scenario, not a causal estimate.
9. **How do you ensure refresh quality?** Explicit Power Query types, deterministic review selection, cleaning log, source hashes, duplicate/orphan checks, revenue reconciliation, and Desktop engine/visual tests after refresh.
10. **What are the main limitations?** Historical 2016–2018 snapshot, incomplete edge months, unequal retention follow-up, nonrandom review response, missing refund/margin data, static RFM labels, and observational delivery effects.

