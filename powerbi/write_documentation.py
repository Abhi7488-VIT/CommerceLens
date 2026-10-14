from pathlib import Path
import json
from model_measures import M
OUT=Path(__file__).resolve().parent
r=json.loads((OUT/'validation/source_results.json').read_text());m=r['metrics']
def pct(x):return f'{100*x:.4f}%'
text=f'''# CommerceLens: E-Commerce Revenue & Retention Analytics

## Delivery status and evidence

This package contains a native Power BI project, not a PBIX binary. The project includes four presentation pages and two hidden support pages, an Import semantic model, Power Query transformations, 41 DAX measures, a theme, and reproducible validators. **Draft until Desktop refresh and visual/interaction testing are complete.** Source reconciliation is computed independently in Python from the nine supplied CSV files. Schema validation and TOM parsing do not execute M, compile DAX, or prove visual rendering.

Open `CommerceLens.pbip` in Power BI Desktop. Both sibling folders (`CommerceLens.Report` and `CommerceLens.SemanticModel`) must stay next to it. The project uses Microsoft's PBIR report format and a supported JSON semantic model (`model.bim`). No data is published or uploaded by the build scripts.

## Business contract

Revenue is **item price plus freight**, across all order statuses unless the user filters status. It represents gross order value, not recognized accounting revenue or net revenue after refunds. Olist provides no refund ledger, margin, acquisition spend, or reliable cancelled-order reversal amount. This deliberately differs from the repository's earlier Streamlit definition (delivered item price, excluding freight). There is no currency conversion: all amounts are Brazilian reais.

Orders counts one row per order, including orders without item lines. AOV divides selected item revenue by matching order count. When a category is selected, AOV is selected-category spend per matching order, not the full basket AOV. Category order counts overlap when an order includes several categories; totals count distinct orders rather than summing category order counts.

Delivery and review measures intersect current status selection with `delivered` using KEEPFILTERS. Selecting a non-delivered status produces blank/zero delivery results rather than silently replacing the slicer. Dates refer to purchase date, including delivery/review analyses, so these are purchase cohorts rather than delivery-month cohorts.

Late means `Date.From(delivered timestamp) > Date.From(estimated timestamp)`. The promised timestamp is a date at midnight; comparing full timestamps would incorrectly label same-day arrivals late. Missing dates are not on-time. Lateness denominator includes only delivered orders with both dates. Review denominator includes only delivered orders with a latest valid 1–5 score. Cohort comparisons also require known lateness.

## Model and relationships

```mermaid
flowchart LR
  D[dim_date: one row per calendar day] --> O[fact_orders: one row per order]
  C[dim_customer: one row per unique person] --> O
  G[dim_state: one row per customer order state] --> O
  O --> I[fact_order_items: one row per order item]
  P[dim_product: one row per product] --> I
  S[dim_seller: one row per seller] --> I
```

All six relationships are active, single-direction, one-to-many from dimension/parent to fact/child. No bidirectional or many-to-many relationships exist. The order-header / item-detail extension is necessary: a single order may contain multiple products and sellers. Joining their keys into one order row would either lose information or multiply order revenue. Customer state filtering uses the address on each order, through dim_state; dim_customer city/state records the latest observed address and is not the geography slicer.

Product and seller dimensions filter item rows. Order-grain measures explicitly transfer the resulting distinct order IDs using TREATAS only when product or seller filtering exists. Without those filters, orders lacking item rows remain included. Date and customer filters flow through the order header to its items. Revenue always sums the item fact; payment totals are aggregated separately and never joined at raw payment × item grain.

`dim_date` covers complete calendar years from the first through last purchase year, with a unique non-null Date key and model Time metadata. Date is marked through `dataCategory=Time` and `isKey=true`; verify Desktop recognizes it under Mark as date table. Month name sorts by month number. Week is Power Query week-of-year with Monday start, **not an ISO week-year**. Auto date/time is disabled in model annotations. Keys and unused fact fields are hidden; seller ID remains available to the authored table even though hidden from general field browsing. All descriptive attributes and bins are produced in Power Query, not DAX calculated columns.

All 41 measures live on `fact_orders` (Power BI Desktop reserves the table name `Measures`). Disconnected tables: `Late Reduction %` (0–1 in 0.05 steps), `Scenario` (Before/After). `cleaning_log` is a hidden audit table and has no relationships.

## RFM segmentation

RFM is a static refresh-time snapshot as of **{m['rfm_asof']}**, one day after the last observed purchase. It uses delivered purchases only; recency is days since last delivered purchase, frequency is delivered order count, monetary is delivered price plus freight. Median customer monetary value is **R${m['rfm_median']:,.2f}**. Segment rules run in this order:

1. Champions: recency ≤90 days, frequency ≥2, monetary ≥ population median.
2. Loyal: recency ≤180 days and frequency ≥2.
3. Lost: recency >365 days.
4. At Risk: recency >180 days.
5. New: remaining customers, including people without delivered purchases.

These mutually exclusive business thresholds are explicit and adjustable. “New” is the low-frequency/recent residual, not a claim that every member is a first-time buyer. Segment charts count customers with delivered orders in the current selection; customers with no delivered orders are not shown. Slicers change segment counts, not the historical RFM label. Repeat purchase rate is dynamic in current filters and is not cohort-normalized retention; late entrants have less follow-up time.

## Cleaning log

The complete steps C01–C16 run once in `export_star_schema.py` (commented there) and are emitted as `data/cleaning_log.csv`. Each Power Query table only reads its own CSV, promotes headers and sets types.

| Step | Treatment |
|---|---|
| C01–C02 | UTF-8 CSV; promote headers; trim strings; blank text becomes null; explicit culture/types |
| C03 | Deduplicate order ID, latest purchase first then customer ID |
| C04 | Deduplicate transaction customer ID deterministically; retain person ID mapping |
| C05 | Remove exact duplicate item rows; composite order/item key preserved; Currency types |
| C06 | Remove exact duplicate payment rows; retain legitimate split tenders; aggregate by order |
| C07 | Latest review answer, then creation timestamp, then review ID; {m['duplicate_review_rows']:,} superseded rows removed; invalid scores become null |
| C08 | Item-less orders retained with zero item revenue and count; missing payment stays null |
| C09 | Calendar-day durations; {m['missing_delivery_dates']} delivered orders missing dates excluded from lateness denominator |
| C10 | Five-day delay bins computed in M; negative bins retain early deliveries |
| C11 | Consolidate customer_unique_id using latest observed order address |
| C12 | Delivered-only snapshot RFM; explicit thresholds above |
| C13 | {m['missing_categories']} products lack category; label Unknown. Untranslated labels retain original Portuguese with prefix |
| C14 | Deduplicate state/ZIP/latitude/longitude points; reject impossible geographic coordinates; average valid points by state for map anchors |
| C15 | Full-year continuous calendar generated from purchase range |
| C16 | {m['missing_reviews_delivered']} delivered orders without valid reviews excluded from rating/review denominators |

Translation gaps: {', '.join(m['untranslated_categories'])}. Geolocation centroids are visualization anchors derived from observed postal points, not authoritative state centroids or customer locations. No comments, review text, product dimensions, raw ZIP fields or unused timestamps are loaded into the final model. Source files remain unchanged. Input SHA-256 hashes are in `validation/source_results.json`.

## Mandatory validation results — local source snapshot

| Check | Result | Exact observed value |
|---|---|---|
| Total orders ≈99,441 | PASS | {m['orders']:,} |
| Late vs on-time low-review share ≈62% / 9% | PASS | {m['late_low_count']:,}/{m['late_reviewed']:,} = {pct(m['low_late'])}; {m['ontime_low_count']:,}/{m['ontime_reviewed']:,} = {pct(m['low_ontime'])} |
| Delivered average rating ≈4.16 | PASS | {m['avg_rating']:.12f}, on {m['reviewed_delivered_orders']:,} reviewed delivered orders |
| Revenue = source price + freight | PASS | R${m['revenue']:,.2f}; aggregate difference < R$0.005 |
| Unique dimension keys and no orphan fact keys | PASS | Customer/product/seller keys unique after stated person consolidation; zero source order/customer and item/order/product/seller orphans |

Tolerance was defined as ±2 percentage points for approximate review shares and ±0.02 stars for rating. No values were changed to fit benchmarks. There are {m['delivered_orders']:,} delivered orders, {m['eligible_deliveries']:,} with usable delivery dates, and {m['late_orders']:,} late orders ({pct(m['late_pct'])}). There are {m['late_reviewed']:,} reviewed late orders versus {m['ontime_reviewed']:,} reviewed on-time orders. Eight reviewed delivered orders with unknown delay contribute to overall rating but not either delivery cohort.

Python validates source keys and equivalent transformations; only a successful Desktop refresh followed by engine queries can prove parity with the loaded Power Query model. `validation/schema_results.json` records PBIR schema validation separately. `validate_model.ps1` uses installed Microsoft TOM libraries to parse the BIM.

## Page-by-page narrative and interaction design

**1 — Executive Summary.** Five KPI cards show revenue, orders, AOV, delivered rating and late share. The monthly line chart shows gross sales; hover for MoM in the custom report-page tooltip. Startup months have very small revenue bases, so plotting MoM on a second axis would obscure meaningful variation. Partial opening/closing months must not be presented as like-for-like growth. The ten-category bar and dynamic insight summarize concentration. At the unfiltered snapshot: R${m['revenue']:,.2f}, {m['orders']:,} orders, R${m['aov']:.2f} AOV, {m['avg_rating']:.2f}/5 rating, {100*m['late_pct']:.2f}% late. The top ten categories generate {100*m['top10_share']:.2f}% of revenue.

**2 — Delivery & Reviews.** The dynamic headline states the observed low-review cohort gap. A 100% stacked score distribution complements a labeled low-review bar comparison. Five-day delay histogram preserves early arrivals. Map bubbles size lateness rate and tooltips show the numerator and denominator; rates in small states are less stable. The decomposition tree offers delivery group, state and category. Use these as descriptive associations, not causal drivers. The default gap is {m['gap_pp']:.4f} percentage points.

**3 — Scenario Simulator.** The disconnected numeric slider defaults to 50%. Three cards and two before/after comparisons show expected late orders avoided, estimated low reviews avoided, and projected rating. The report never overwrites historical facts. At 50%: {m['late_avoided']:,.0f} late orders avoided, {m['low_avoided']:,.4f} expected low reviews avoided, projected rating {m['projected_rating']:.6f}/5. Cards round display counts, while measures retain fractional expectations.

**4 — Customers & Geography.** A five-segment donut, customer count by segment, state revenue, repeat-rate/customer cards and seller table support prioritization. Repeat rate is {pct(m['repeat_pct'])}: {m['repeat_customers']:,} repeat customers among {m['delivered_customers']:,} delivered customers. Seller revenue follows line attribution; seller order/review metrics count matching orders and may overlap across sellers.

There are 6–8 analytical visuals per presentation page; navigation, four shared slicers, titles and source notes are additional controls. All pages use 1280×720 canvases, Segoe UI, navy and teal with a gold accent, white plot surfaces and neutral gray background. Every visual has alt text and a defined tab order. Gold is used as a graphical accent, not low-contrast body text. Charts also provide labels/legends so color is not the only signal.

Date range, customer order state, category and order status slicers share sync groups. Reset restores unfiltered shared slicers and 50% scenario without changing the current page. Navigation buttons link all four pages. Hidden Tooltip is attached to revenue trend and map; hidden Detail binds state/category drill-through filters and provides an order table. In Desktop edit mode, use Ctrl+click for navigation actions. Test tooltip hover, right-click drill-through, cross-page filter synchronization, and reset before presentation.

## Scenario assumptions

`Late Orders Avoided = Late Orders × Late Reduction %`.

`Low Reviews Avoided = Late Orders Avoided × (Low Review % Late − Low Review % On-time)`.

The low-review formula extrapolates rates from reviewed orders to all late orders, including those without reviews. A negative observed gap is retained, not silently clipped. If either reviewed cohort is missing, scenario benefits are blank.

Projected rating shifts the selected fraction of **reviewed** late orders from the late mean rating to the on-time mean, keeping total reviewed volume fixed:

`Baseline rating + (Late reviewed orders × reduction × (On-time mean − Late mean)) / Delivered reviewed orders`.

The rating is bounded to the valid 1–5 scale. This uses full score distributions rather than inventing how many stars a “saved” low review receives. It assumes cohort comparability, no change in review propensity and no other operational changes. Observational data cannot establish those assumptions; validate through a pilot or randomized intervention before forecasting financial benefits.

## Measures

All measures are on the `fact_orders` table, grouped with display folders. Full, commented DAX and format strings appear in `measures.dax`, which can be pasted into DAX query view.

| Measure | Meaning | Format |
|---|---|---|
'''
for x in M:text+=f"| {x['name']} | {x['description']} | `{x['formatString']}` |\n"
text+='''
## Refresh and presentation handoff

1. Run `python powerbi/export_star_schema.py` to turn the nine raw Olist CSVs (repository root) into the star-schema CSVs in `powerbi/data`. The default source is `C:\\CommerceLens\\powerbi\\data`; change the `DataFolder` parameter (Transform data > Edit parameters) if they live elsewhere.
2. Open `powerbi/CommerceLens.pbip` in a current Power BI Desktop supporting PBIP/PBIR. If requested, enable the project/report-format preview features and restart Desktop yourself.
3. Refresh. File-source privacy/security prompts must be reviewed by the user. Do not publish or configure cloud credentials to run this local report.
4. Inspect `cleaning_log`, row counts and the measures against the validation table. Confirm dim_date is recognized as the marked date table and the six relationships are single-direction.
5. If map visuals are disabled by Desktop policy, enable them yourself only if acceptable under your policy; alternatively use a state-rate bar. Map rendering may require network access. The agent does not change security/privacy settings.
6. Verify all page visuals, parameter endpoints (0%, 50%, 100%), synced slicers, Reset, tooltip and drill-through. At 0% avoided counts must be zero and projected rating equal baseline; at 100% the cohort remains bounded to the on-time mean contribution.
7. Save in Desktop. Use Save As → PBIX to produce `CommerceLens.pbix` if desired. PBIX binary generation is performed by Desktop, not by editing or fabricating a binary file.
8. Export one PNG screenshot per visible report page after refresh and visual verification. Screenshots must be captures of the rendered Power BI report; offline previews, if supplied, are explicitly labeled and are not evidence of Desktop rendering.

For reproducibility run `export_star_schema.py`, `build_commercelens.py`, `build_model.py`, `build_report.py`, `validate_project.py`, then `write_documentation.py` with the repository Python environment. Regeneration overwrites generated report/model definitions, so preserve any manual Desktop changes first. `export_star_schema.py` is the production transformation path; `build_commercelens.py` is an independent pandas reconciliation of the raw sources. Do not regenerate over an open, modified Desktop project.

## Top 5 insights for a non-technical client

'''
insights=[f'The marketplace recorded R${m["revenue"]:,.2f} in gross order value across {m["orders"]:,} orders, with R${m["aov"]:.2f} per order. These figures include freight and all statuses, so they are not net recognized revenue.',f'Late delivery is associated with a much worse experience: {100*m["low_late"]:.2f}% of late orders received 1–2 stars versus {100*m["low_ontime"]:.2f}% on-time, a {m["gap_pp"]:.2f}-point gap.',f'Late deliveries are a minority with disproportionate dissatisfaction: {m["late_orders"]:,} of {m["eligible_deliveries"]:,} eligible delivered orders were late ({100*m["late_pct"]:.2f}%). Prioritize reducing this exposure.',f'The top ten product categories account for {100*m["top10_share"]:.2f}% of gross revenue. Health & beauty leads at R${m["top_category_revenue"]:,.2f}, giving a focused starting point for operational pilots.',f'Repeat purchasing is limited in this observation window: {m["repeat_customers"]:,} of {m["delivered_customers"]:,} delivered customers bought at least twice ({100*m["repeat_pct"]:.2f}%). Test lifecycle outreach, while adjusting future analysis for unequal customer follow-up.']
for i,x in enumerate(insights,1):text+=f'{i}. {x}\n'
text+='''
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

## Format references

- [Microsoft: Power BI project report folders and PBIR](https://learn.microsoft.com/power-bi/developer/projects/projects-report)
- [Microsoft: Power BI Desktop projects](https://learn.microsoft.com/power-bi/developer/projects/projects-overview)
- Microsoft JSON schemas are downloaded under `schemas/cache` for repeatable report checks. Embedded schema URLs are normalized from `.embedded` to `-embedded` where Microsoft's declared IDs differ from served URLs.
'''
(OUT/'DOCUMENTATION.md').write_text(text,encoding='utf-8')
(OUT/'validation/RESULTS.md').write_text(text[text.index('## Mandatory validation'):text.index('## Page-by-page')],encoding='utf-8')
(OUT/'INTERVIEW_QA.md').write_text(text[text.index('## Ten likely'):text.index('## Format references')],encoding='utf-8')
print('Documentation, validation results and interview Q&A written')
