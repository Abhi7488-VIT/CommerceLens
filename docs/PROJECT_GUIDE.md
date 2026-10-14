# CommerceLens — Project Guide

A complete walkthrough of the project: why it exists, what it does, how each part works, the numbers it produced, the decisions behind it, and how to talk about it in interviews.

All figures in this guide come from the project's code (the `sql/` queries, the three notebooks and `scripts/build_dashboard_data.py`) run on the Olist dataset. If you re-run the pipeline and a model metric moves slightly (different CPU), trust the notebook output over this file.

---

## Table of contents

1. [Elevator pitch](#1-elevator-pitch)
2. [Why this project](#2-why-this-project)
3. [The dataset](#3-the-dataset)
4. [Architecture and data flow](#4-architecture-and-data-flow)
5. [Tech stack and why each tool](#5-tech-stack-and-why-each-tool)
6. [Repository walkthrough](#6-repository-walkthrough)
7. [Layer 1 — SQL analytics](#7-layer-1--sql-analytics)
8. [Layer 2 — Insight to action](#8-layer-2--insight-to-action)
9. [Layer 3 — The model](#9-layer-3--the-model)
10. [The dashboard](#10-the-dashboard)
11. [Key numbers cheat sheet](#11-key-numbers-cheat-sheet)
12. [Decisions, trade-offs and bugs fixed](#12-decisions-trade-offs-and-bugs-fixed)
13. [Limitations and what I would do next](#13-limitations-and-what-i-would-do-next)
14. [Interview questions and answers](#14-interview-questions-and-answers)
15. [Glossary](#15-glossary)
16. [How to run it](#16-how-to-run-it)

---

## 1. Elevator pitch

**30-second version**

> CommerceLens analyses about 100,000 orders from Olist, a Brazilian e-commerce marketplace. It answers one question at increasing depth: where revenue is concentrated, and which operational factors drive customer satisfaction and repeat purchases. I used DuckDB SQL to analyse the raw data, statistical tests to find the drivers, and a LightGBM model with SHAP to predict bad reviews at checkout. The headline finding is that late delivery is the dominant cause of bad reviews: late orders are 6.7% of orders but get a 1-2 star review 62.4% of the time, against 9.3% for on-time orders. Freight price barely matters. It's all in a live Streamlit dashboard with what-if simulators.

**2-minute version (structure to follow)**

1. **Problem:** a marketplace needs to know where its money comes from and why customers are unhappy or don't return.
2. **Data:** 9 relational tables, about 100k orders, 2016–2018.
3. **Layer 1 (analyst):** SQL shows revenue is concentrated. 18 of 74 categories make 80% of revenue, the top 20% of sellers make 82.3%, and 97% of customers buy only once.
4. **Layer 2 (consultant):** late delivery is 6.7x worse for reviews, it is regional (RJ is late 12.1% of the time vs 4.5% in SP), and freight price and first-order experience barely matter.
5. **Layer 3 (data scientist):** I compared two targets, picked low-review prediction because repeat purchase had too little signal, built leakage-free features, and reported an honest out-of-time score (ROC-AUC 0.611) next to the random-split score (0.673).
6. **Impact:** flagging the riskiest 10% of orders at checkout catches 25.6% of future bad reviews, at 2.6x the rate of random picking.

---

## 2. Why this project

### The business question (the "anchor question")
> *Where is revenue concentrated, and which operational factors (delivery time, freight cost, product category, region) drive customer satisfaction and repeat purchases?*

Every part of the project answers this one question, and each layer goes deeper:

| Layer | Role it demonstrates | Question it answers |
|---|---|---|
| 1. SQL analytics | Data Analyst | *Where* is revenue, and who are the customers? |
| 2. Insight → Action | Consultant | *Why* are customers unhappy, and *what should the business do*? |
| 3. Model | Data Scientist | Can we *predict* the problem early enough to act? |

### Why this design
- **One question, three depths.** Many portfolio projects are a pile of unrelated charts. Here every chart, test and model serves the same question, which is how real analytics work is judged.
- **Different readers can stop at different points.** A hiring manager for an analyst role can stop after Layer 1, a consulting interviewer after Layer 2.
- **The insight is the hero, not the infrastructure.** There is no Docker and no heavy test suite. The effort went into correctness (leakage, censoring, reproducibility) and into clear business recommendations.
- **Honesty is a feature.** The project reports its limitations, rejects a weak model target, and shows the less flattering out-of-time metric. Interviewers trust candidates who do this.

---

## 3. The dataset

**Source:** the Olist Brazilian E-Commerce Public Dataset on Kaggle (`olistbr/brazilian-ecommerce`), licensed CC BY-NC-SA 4.0. It is real, anonymised marketplace data from 2016 to 2018.

### The 9 tables and how they join

```
customers ──(customer_id)──> orders <──(order_id)── order_items ──(product_id)──> products ──> category_translation
                                │                          │
                                │                          └──(seller_id)──> sellers
                                ├──(order_id)── payments
                                └──(order_id)── reviews
geolocation  (zip_code_prefix → lat/lng, joined to customers and sellers by zip prefix)
```

| Table | Grain (one row per…) | Used for |
|---|---|---|
| `orders` | order | status, purchase/approval/carrier/delivery/estimated dates |
| `order_items` | item in an order | price, freight, product, seller |
| `customers` | `customer_id` (one per order!) | `customer_unique_id`, state, zip |
| `products` | product | category, weight, dimensions, photos |
| `sellers` | seller | state, zip |
| `payments` | payment in an order | payment type, installments |
| `reviews` | review | review score (1–5) |
| `geolocation` | zip prefix + coordinate | seller→customer distance |
| `category_translation` | category | Portuguese → English names |

### Data quirks you must know (common interview topics)
1. **`customer_id` is not a customer.** Olist issues a new `customer_id` for every order. The real person is `customer_unique_id`. Counting customers by `customer_id` would make every repeat buyer look new, so all customer-level work uses `customer_unique_id`.
2. **Some orders have more than one review.** I keep the latest one per order with `ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC)`.
3. **Zip-code prefixes have leading zeros** (e.g. "01037"), so they are loaded as text, not numbers.
4. **Sparse edge months.** Late 2016 and September–October 2018 have very few orders, so they are flagged (under 500 orders) and excluded from trend analysis.
5. **Geolocation has many rows per zip prefix, plus some points outside Brazil.** I average the coordinates per prefix and drop points outside Brazil's bounding box.
6. **Estimated delivery dates are conservative.** 92.0% of orders arrive early, which matters for how customers judge lateness.

### Definitions used everywhere
| Term | Definition |
|---|---|
| Revenue | Sum of item `price` on **delivered** orders (freight excluded, analysed separately) |
| Customer | `customer_unique_id` |
| Late | Delivered after `order_estimated_delivery_date` (compared as dates) |
| Low review | Review score 1 or 2 |
| Repeat customer | 2 or more delivered orders |

---

## 4. Architecture and data flow

```
                ┌──────────────────────────────────────────────┐
  9 raw CSVs ──>│ DuckDB (in-memory) — CSVs registered as views│  src/db.py
  (repo root,   │ sql/00_base_views.sql → cleaned joined views │
   gitignored)  └──────────────────────┬───────────────────────┘
                                       │ runs the sql/*.sql files
         ┌─────────────────────────────┼────────────────────────────┐
         ▼                             ▼                            ▼
  notebooks/01_sql_analytics   notebooks/02_insights        notebooks/03_model
  (Layer 1: SQL results,       (Layer 2: drivers, tests,    (Layer 3: features via
   charts)                      findings table)              sql/18, LightGBM, SHAP)
                                       │                            │
                                       └──────────┬─────────────────┘
                                                  ▼
                            scripts/build_dashboard_data.py
                            (same SQL + same model code → 25 small parquet files, 383 KB)
                                                  ▼
                            dashboard/app.py (Streamlit) — reads ONLY dashboard/data/*.parquet
                                                  ▼
                                   Streamlit Community Cloud (live link)
```

**Design principles**
- **SQL is the single source of truth.** The notebooks, the build script and therefore the dashboard all run the same `.sql` files, so a number can't differ between the notebook and the dashboard.
- **The dashboard never touches the raw data.** It reads small pre-aggregated parquet files, which is what makes free cloud deployment possible (the raw CSVs total about 126 MB and are not in git).
- **One config setting:** `src/config.py` defines `DATA_DIR`. It defaults to the repo root and can be overridden with the `COMMERCELENS_DATA_DIR` environment variable. All paths use `pathlib`, so the same code runs on Windows and Linux.

---

## 5. Tech stack and why each tool

| Tool | What it does here | Why this and not an alternative |
|---|---|---|
| **Python 3.11** | Everything | Stable, fully supported by every library used |
| **DuckDB** | Runs SQL directly on the CSV files | No database server to install; columnar and very fast for analytics; full SQL including CTEs and window functions. Postgres needs a server and a data load step; pandas alone wouldn't show SQL skill |
| **pandas / NumPy** | Post-processing, small calculations | Standard for tabular data in Python |
| **SciPy** | z-test, chi-square, Spearman correlation | Standard, trusted statistical tests |
| **LightGBM** | Gradient-boosted trees for the risk model | Handles categorical features natively, fast, strong on tabular data. XGBoost would work equally well; LightGBM's native categorical support meant less preprocessing |
| **scikit-learn** | Train/test split, logistic-regression baseline, metrics | Standard ML toolkit |
| **SHAP** | Explains the model | Explains each prediction as a sum of feature contributions and is consistent across features; better than built-in "feature importance", which is biased toward high-cardinality features |
| **matplotlib** | Static charts in the notebooks | Renders on GitHub (Plotly charts don't render in GitHub's notebook viewer) |
| **Plotly** | Interactive charts in the dashboard | Hover, zoom and click events |
| **Streamlit** | The web dashboard | Pure Python and free cloud hosting. Power BI isn't free to share publicly, which is why `docs/powerbi_notes.md` explains how to rebuild it there |
| **Parquet (pyarrow)** | Dashboard data files | Columnar, compressed and typed. 25 files total only 383 KB |
| **Jupyter / nbconvert** | Notebooks, executed headlessly | Outputs are saved, so recruiters can read results on GitHub without running anything |

---

## 6. Repository walkthrough

```
check_data.py                   verifies the 9 CSVs exist; prints the Kaggle URL if any are missing
src/config.py                   DATA_DIR setting (+ env override), list of required files
src/db.py                       DuckDB connection; registers CSVs as views; runs .sql files
src/features.py                 builds the two model datasets (low review, repeat purchase)
src/model.py                    split, LightGBM training, logistic baseline, metrics, SHAP
sql/00–20                       every query, one question per file
notebooks/01_sql_analytics      Layer 1
notebooks/02_insights           Layer 2 (+ Findings & Recommendations table)
notebooks/03_model              Layer 3
scripts/build_dashboard_data.py raw data → dashboard/data/*.parquet
dashboard/app.py                Streamlit app (6 pages)
dashboard/requirements.txt      slim dependencies for Streamlit Cloud
.streamlit/config.toml          dashboard theme
docs/powerbi_notes.md           how to rebuild the dashboard in Power BI
```

### SQL file index
| File | Purpose | Key technique |
|---|---|---|
| `00_base_views.sql` | Joined, cleaned views used by everything | Multi-table JOINs, `ROW_NUMBER()` dedup |
| `01_order_status.sql` | Orders by final status | Window share `SUM(COUNT(*)) OVER ()` |
| `02_order_funnel.sql` | Timestamp-based fulfilment funnel | `UNION ALL`, `FIRST_VALUE`, `LAG` |
| `03–05_pareto_*.sql` | Revenue concentration (category/seller/state) | Running sum `ROWS UNBOUNDED PRECEDING` |
| `06_monthly_trend.sql` | Monthly revenue, orders, AOV, growth | `DATE_TRUNC`, `LAG` |
| `07_order_frequency.sql` | Orders per customer | CTE + distribution |
| `08–09_rfm_*.sql` | RFM segmentation | `NTILE(5)` |
| `10_kpis.sql` | Headline KPIs | Scalar subqueries |
| `11–12` | Delivery delay vs review | `CASE` bucketing |
| `13–14` | Category and state operations scorecards | Multi-CTE aggregation |
| `15` | Freight share vs review | `FILTER (WHERE …)` aggregate |
| `16` | First order vs 180-day repeat | `LEAD`, right-censoring guard |
| `17` | Top 20% sellers vs the rest | `PERCENT_RANK` |
| `18_order_features.sql` | Leakage-free model features | Haversine distance, prior-order counts with `ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING` |
| `19_repeat_target.sql` | Repeat-purchase target | `LEAD` + censoring guard |
| `20_monthly_ops.sql` | Monthly lateness and review health | Aggregation by month |

---

## 7. Layer 1 — SQL analytics

**Notebook:** `notebooks/01_sql_analytics.ipynb`

### How it works
1. `src/db.py` opens an in-memory DuckDB connection and registers each CSV as a view (`CREATE VIEW orders AS SELECT * FROM read_csv(...)`). No data is copied.
2. `sql/00_base_views.sql` builds three views:
   - `order_items_enriched`: items + English category + seller state + customer + order status.
   - `order_reviews_latest`: one review per order.
   - `orders_enriched`: one row per order with value, freight, item count, review, `delay_days` (actual minus estimated delivery) and `delivery_days`.
3. Each analysis is one `.sql` file that the notebook loads and runs.

### What it found
| Metric | Value |
|---|---|
| Delivered orders / all orders | 96,478 / 99,441 |
| Revenue | R$13,221,498 |
| Average order value | R$137.04 |
| Unique customers | 93,358 |
| Orders reaching the customer | 97.0% |
| Categories producing 80% of revenue | 18 of 74 (top 10 = 62.4%) |
| Revenue from top 20% of sellers | 82.3% (533 sellers, 17.9%, cover 80%) |
| Revenue from SP + RJ + MG | 63.4% (SP alone 38.3%) |
| Jan–Aug revenue growth, 2018 vs 2017 | +141.1% |
| Peak month | November 2017 (R$987,765, Black Friday) |
| Customers who bought only once | 97.0% (repeat rate 3.00%) |
| RFM "Champions" | 16.5% of customers, 31.6% of revenue |

### The funnel
Built from **timestamps**, not just the final status, so it shows where orders drop out:
Purchased (99,441) → Payment approved (99.8%) → Handed to carrier (98.2%) → Delivered (97.0%).

### Pareto analysis
The cumulative revenue share is a running window sum:
```sql
SUM(revenue) OVER (ORDER BY revenue DESC ROWS UNBOUNDED PRECEDING) / SUM(revenue) OVER ()
```

### RFM, and why Frequency isn't scored
- **R**ecency = days since last purchase, measured from the day after the last purchase in the data (not today, because the data ends in 2018).
- **M**onetary = total spend.
- Both are split into quintiles with `NTILE(5)`, where 5 is best.
- **Frequency is not scored**, because 97% of customers bought once. A frequency quintile would randomly split thousands of identical "1 order" customers into different groups. Frequency is kept as a simple repeat-buyer flag instead.

| Segment | Rule | Customers | Revenue |
|---|---|---|---|
| Champions | R ≥ 4 and M ≥ 4 | 16.5% | 31.6% |
| At risk, high value | R ≤ 2, M ≥ 4 | 15.6% | 30.6% |
| Potential loyalists | R = 3, M ≥ 4 | 7.9% | 14.2% |
| Hibernating | R ≤ 2, M ≤ 3 | 24.4% | 9.7% |
| Recent, low spend | R ≥ 4, M ≤ 3 | 23.5% | 9.3% |
| Needs attention | R = 3, M ≤ 3 | 12.1% | 4.7% |

---

## 8. Layer 2 — Insight to action

**Notebook:** `notebooks/02_insights.ipynb`

### What it tests and how
| Question | Method |
|---|---|
| Does lateness hurt reviews? | Low-review rate by delay bucket (8 buckets from "15+ days early" to "15+ days late") |
| Is it regional? | Per-state late rate vs low-review rate, order-weighted correlation |
| Which categories are problems? | Per-category scorecard (categories with at least 300 orders) |
| Does freight price matter? | Low-review rate by freight share of price, **on on-time orders only**, to remove the lateness effect |
| Are top sellers the problem? | Top 20% of sellers vs the rest |
| Does a bad first order stop repeat purchases? | 180-day repeat rate by first-order experience; two-proportion z-test and chi-square test |

### Key results
- **Lateness:** late orders are 6.7% of reviewed orders. They get a 1-2★ review 62.4% of the time vs 9.3% on time (6.7x) and produce 32.4% of all low reviews.
  - Even 1–3 days late gives a 32.1% low-review rate.
  - Arriving exactly on the estimated day already gives 12.4%, against about 9% for early deliveries. Customers judge delivery against the promise.
- **Upper bound:** if late orders were reviewed like on-time ones, about 3,392 low reviews (27.6% of all) would not happen. It's an upper bound because it assumes lateness fully causes the difference.
- **Region:** RJ (13.3% of revenue) is late 12.1% of the time vs 4.5% in SP (2.7x), with 18.3% vs 10.7% low reviews.
  - Across states, late rate and low-review rate are almost perfectly related (order-weighted r = 0.95).
  - CE, MA, PI, AL and SE run at 2x or more the national late rate (6.8%).
- **Category:** office_furniture has 21.9% low reviews vs 12.8% overall and takes 20.6 days on average to deliver.
- **Freight:** on on-time orders, the low-review rate only moves from 8.75% to 9.80% between the cheapest and most expensive freight share (1.05 points), against a 53.2-point gap for lateness. Across categories, Spearman rho = −0.04 (p = 0.822).
- **Sellers:** the top 20% are late 6.79% of the time vs 6.59% for the rest, so lateness is not a small-seller problem.
- **Retention:** the 180-day repeat rate is 3.10% (n = 55,907). A late first order gives 2.65% vs 3.14% (z = −1.68, p = 0.093, not significant at 5%). First review score shows no link (chi-square p = 0.775).

### Findings & Recommendations (problem → finding → so what → action)
| # | Problem | Finding | So what | Action |
|---|---|---|---|---|
| 1 | What hurts satisfaction most? | Late: 62.4% vs 9.3% low reviews | Biggest lever on ratings | On-time delivery as the #1 KPI; flag at-risk orders at purchase; carrier SLAs |
| 2 | Is it regional? | RJ 12.1% late vs SP 4.5%; r = 0.95 | Fix specific delivery routes, not the whole platform | Audit carriers on SP→RJ and North-East routes |
| 3 | Which categories? | office_furniture 21.9% low reviews | Slow, bulky categories carry a penalty | Category-specific delivery promises and packaging |
| 4 | Does freight matter? | 1.05-point gap vs 53.2 for lateness | Weak driver | Fund reliability, not shipping subsidies |
| 5 | Is seller concentration a risk? | Top sellers are late at the same rate | Pruning small sellers won't help | Key-account support for top sellers |
| 6 | Why no repeat buyers? | 97.0% buy once; no significant experience effect | Retention is structural | Lifecycle CRM, starting with "At risk, high value" (30.6% of revenue) |

### Why the 180-day window and the "censoring guard"
A customer who first bought a week before the data ends has had no time to come back. Counting them as "did not return" would wrongly lower the repeat rate. The guard keeps only customers whose first order is at least 180 days before the end of the data, so everyone has had the same chance to return. This problem is called **right-censoring**.

---

## 9. Layer 3 — The model

**Notebook:** `notebooks/03_model.ipynb` · **Code:** `src/features.py`, `src/model.py`, `sql/18_order_features.sql`

### Step 1: choosing the target
Both candidate targets were built and scored with the same pipeline:

| Target | Positive rate | ROC-AUC | PR-AUC (× base rate) | Precision in top 10% |
|---|---|---|---|---|
| Repeat purchase within 180 days | 3.1% | 0.612 | 0.048 (1.54x) | 5.2% |
| **Low review (1-2★)** ✅ | 12.8% | 0.673 | 0.269 (2.10x) | 32.8% |

**Decision rule, applied in code:** pick the target with the higher PR-AUC lift. Repeat purchase is rare and barely predictable (it matches Layer 2's finding that experience doesn't move it), and even the riskiest 10% of customers are 94.8% non-returners. Low review has usable signal and is directly actionable.

### Step 2: features, made at purchase time
**Prediction time = the moment the order is placed.** A feature is allowed only if it is known at that moment.

| Used (24 features) | Excluded to prevent leakage |
|---|---|
| Order value, freight, freight ratio, item/product/seller counts | Actual delivery date, carrier hand-off date |
| Promised delivery window (estimated date − purchase date) | `delay_days` (only known after delivery) |
| Purchase month, day of week, hour | Order approval timestamp |
| Main category, total weight, max volume, photo count, description length | Anything from the review itself |
| Payment type, installments, number of payment types | Future orders of the customer |
| Customer state, seller state, same-state flag, seller→customer distance (haversine) | |
| Seller's and customer's **prior** order counts | |

**The prior-order counts** are computed with a window that only looks backwards:
```sql
COUNT(*) OVER (PARTITION BY seller_id ORDER BY order_purchase_timestamp, order_id
               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
```
It counts strictly earlier orders, never the current or future ones.

**Distance** is the haversine (great-circle) distance between the averaged coordinates of the seller's and the customer's zip prefixes.

### Step 3: training
- **Stratified 80/20 train/test split,** so both sets have the same 12.8% positive rate.
- **LightGBM** with learning rate 0.03, 31 leaves, a minimum of 50 samples per leaf, 80% row and column subsampling, and L2 regularisation.
- **Early stopping** on an *inner* validation split carved from the training set. The test set is never used during training, so test metrics stay honest.
- **Deterministic mode** (`deterministic=True`, fixed seed, sorted input rows), so results are reproducible.
- **Baselines:** a no-skill baseline (ROC-AUC 0.5; PR-AUC equals the positive rate) and a logistic regression on the same features (one-hot categoricals, scaled numerics).

### Step 4: results
| Model | ROC-AUC | PR-AUC | PR-AUC lift |
|---|---|---|---|
| No-skill baseline | 0.500 | 0.128 | 1.00x |
| Logistic regression | 0.629 | 0.232 | 1.81x |
| **LightGBM (stratified test)** | **0.673** | **0.269** | **2.10x** |
| LightGBM (out-of-time: train before May 2018, test after) | 0.611 | 0.181 | 1.81x (base rate 10.0%) |

**Operational value:** flagging the riskiest 10% of orders catches 25.6% of all low reviews, with 32.8% precision (2.6x random).

### Step 5: the honest robustness check
Low reviews spiked in November 2017 (Black Friday volume) and in February–March 2018. With a random split, the model sees orders from those months in training and learns "this month is bad", so `purchase_month` looks very predictive. The future won't repeat those exact months. Training on the past and testing on the future (the out-of-time test) gives the fair estimate: ROC-AUC 0.611, still 1.81x better than chance on PR-AUC.

### Step 6: SHAP explanation
- **Top drivers (mean |SHAP|):** purchase_month, customer_state, n_items, main_category, seller_state.
- **Highest-risk states:** RJ, BA and PA, the same late-delivery states Layer 2 found.
- **Multi-item orders sharply raise risk** (mean SHAP +0.72 above the median vs −0.08 below), probably because of split shipments and partial deliveries.
- **A longer promised window lowers risk,** and a longer distance raises it. Customers react to delivery against the promise.

### Why moderate AUC is acceptable
At purchase time the model cannot know the single biggest driver, whether the delivery will actually be late. A 0.61–0.67 AUC triage score that finds 2.6x more problem orders than random is useful. The natural next step is to re-score at carrier hand-off, when in-transit signals exist.

---

## 10. The dashboard

**File:** `dashboard/app.py` · **Theme:** `.streamlit/config.toml` · **Data:** 25 parquet files, 383 KB

### Design
Material 3–inspired: a gradient hero banner, a sidebar navigation rail with icons, elevated rounded cards, KPI cards with inline SVG sparklines, Roboto font, and a custom Plotly template so every chart matches. Chart colours use a fixed categorical palette (blue for normal, orange for "late / above average"), and there are no dual-axis charts.

### Pages (deep-linkable with `?page=…`)
| Page | Contents |
|---|---|
| Overview | 8 KPI cards with sparklines, 3 insight cards, funnel, monthly operations health |
| Revenue | Category/seller/state switcher, top-N slider, click-to-inspect profile, Pareto curve, zoomable monthly trend |
| Customers & RFM | Orders-per-customer donut, RFM treemap, segment explorer with recommended actions |
| Satisfaction drivers | What-if simulator, delay vs review, state scatter with click-to-profile, category and freight charts, repeat-rate test |
| Risk model | Model KPIs, triage simulator, ROC/PR curves, SHAP importance, beeswarm, state effects |
| Findings | The 6 findings as cards, plus method and limitations |

### How the two simulators work
**What-if: cut late deliveries by X%**
- Rescued orders = late orders × X%.
- They are assumed to get the on-time low-review rate (9.3%) instead of the late rate (62.4%).
- At 50%: 3,190 orders rescued, 1,696 fewer low reviews (13.8% of all), the low-review rate falls from 12.8% to 11.0%, and the average rating rises from 4.16 to 4.22.
- It's labelled an **upper bound** because it assumes lateness fully causes the gap.

**Triage: flag the riskiest X% of orders**
- It uses the model's capture curve (the share of low reviews found in the top X% of risk scores).
- At 10%: about 481 orders flagged per month (average 4,811 delivered orders per month), catching 25.6% of low reviews, with 32.8% of flagged orders actually turning out 1-2★.

### Why pre-aggregated parquet
- **Speed:** the dashboard loads instantly and never re-runs SQL or the model.
- **Deployability:** Streamlit Cloud gets 0.4 MB instead of 126 MB of CSVs.
- **Consistency:** the build script runs the same SQL and model code as the notebooks.

---

## 11. Key numbers cheat sheet

Memorise these, since they're the ones interviewers ask about.

| Topic | Number |
|---|---|
| Orders / delivered | 99,441 / 96,478 |
| Revenue | R$13.22M |
| AOV | R$137.04 |
| Customers | 93,358 |
| One-time buyers | 97.0% |
| Categories to 80% of revenue | 18 of 74 |
| Top 20% sellers' revenue share | 82.3% |
| SP + RJ + MG revenue share | 63.4% |
| YoY growth (Jan–Aug) | +141.1% |
| Late deliveries | 6.8% of delivered orders (6.7% of reviewed orders) |
| Low reviews: late vs on time | 62.4% vs 9.3% (6.7x) |
| Share of low reviews from late orders | 32.4% |
| RJ vs SP late rate | 12.1% vs 4.5% |
| State correlation (late vs low reviews) | r = 0.95 |
| Freight effect (on-time orders) | 1.05 points vs 53.2 for lateness |
| 180-day repeat: late vs on-time first order | 2.65% vs 3.14% (p = 0.093) |
| Model ROC-AUC / PR-AUC | 0.673 / 0.269 (out-of-time 0.611 / 0.181) |
| Top 10% capture | 25.6% of low reviews, 32.8% precision |

---

## 12. Decisions, trade-offs and bugs fixed

### Key decisions
| Decision | Why |
|---|---|
| Revenue = item price only | Freight is a pass-through cost, and it's analysed separately in Layer 2 |
| Delivered orders only for revenue | Canceled and unavailable orders never became realised revenue |
| `customer_unique_id` for customers | `customer_id` is per order |
| RFM on Recency × Monetary | Frequency is degenerate (97% one-time) |
| 180-day repeat window + censoring guard | A fair comparison, with no penalty for recent customers |
| Freight tested on on-time orders only | Removes the lateness confounder, since expensive-to-ship orders are also late more often |
| Low review over repeat purchase as the target | Much more signal (2.10x vs 1.54x PR-AUC lift) and actionable |
| Purchase-time features only | No leakage; the score can be used at checkout |
| Report the out-of-time score | The random split is optimistic because of time-period effects |
| Keep `purchase_month` | It is known at purchase time, and a with/without comparison during development showed it still helped slightly out of time (about +0.006 ROC-AUC). Its time-period effect is disclosed |
| Parquet for the dashboard | Small, fast, deployable, consistent with the notebooks |

### Bugs found and fixed (good interview stories)
1. **RFM numbers changed between runs.** `NTILE` splits tied values across quintile boundaries arbitrarily, so Champions moved between 16.4% and 16.6%. Fix: add `customer_unique_id` as a deterministic tie-breaker in the `ORDER BY`.
2. **Model metrics changed between runs** (ROC-AUC 0.683 vs 0.669 with the same seed). Cause: the feature query had no `ORDER BY`, so DuckDB returned rows in a different order and the "same" random split picked different rows. Fix: `ORDER BY order_id`, plus LightGBM's `deterministic=True`.
3. **Absurd month-over-month growth** (+1,025,573% in January 2017), because the previous month was a near-empty edge month. Fix: only compute growth when the previous month has at least 500 orders.
4. **The out-of-time check** revealed the random split was optimistic (0.673 → 0.611). It's disclosed rather than hidden.

---

## 13. Limitations and what I would do next

### Limitations
- **Correlation, not causation.** Late → low review is very plausible causally (reviews are written after delivery), but routes, categories and sellers are intertwined, so "avoidable" numbers are upper bounds.
- **One-time-buyer skew** limits any retention modelling.
- **2016–2018 Brazil data.** Carriers, customer expectations and the platform have all changed since.
- **Review coverage:** only delivered orders with a review are scored.
- **No traffic or funnel data:** freight's effect on *conversion* (abandoned carts) can't be measured.
- **The model runs at purchase time,** so it can't see the actual delivery performance.

### Next steps
1. **Second-stage model at carrier hand-off,** using in-transit signals (carrier delay so far, route) to predict lateness and bad reviews much more accurately.
2. **Causal estimate of lateness.** Use a matched comparison or a natural experiment (e.g. the same seller and route, late vs on-time orders) to replace the upper bound with a causal effect.
3. **An A/B test of proactive delay notifications** on flagged orders, measuring review scores.
4. **Delivery-date promise optimisation:** set estimated dates per route to balance conversion (shorter promise) against satisfaction (kept promise).
5. **Review text analysis** (Portuguese NLP) to find *why* late customers complain.
6. **Scheduled data refresh** and model monitoring for drift.

---

## 14. Interview questions and answers

### A. General and behavioural

**Q1. Walk me through your project.**
Use the 2-minute version in section 1: problem → data → three layers → headline numbers → impact.

**Q2. Why did you choose this dataset?**
It's real, relational (9 tables, so real joins are needed), large enough to matter (about 100k orders), and has both commercial data (revenue) and operational data (delivery dates, reviews). That combination lets one project show analyst, consultant and data-scientist skills together.

**Q3. What was the most interesting finding?**
That freight price barely matters for satisfaction, while lateness matters enormously: a 1.05-point effect vs a 53.2-point effect. The intuitive assumption is that expensive shipping angers customers, but once you control for lateness it doesn't.

**Q4. What was the hardest part?**
Keeping the model honest. Leakage is easy to introduce with this data (the delivery date is right there in the orders table), and the time-period effect only showed up when I ran an out-of-time test. Making every result reproducible also took work: I fixed two nondeterminism bugs.

**Q5. What would you do differently?**
Plan the out-of-time evaluation from the start rather than as a check, and design the features around a second prediction point (carrier hand-off), where much more signal exists.

**Q6. How long did it take, and how did you structure it?**
In six stages with a checkpoint after each: scaffold and data check → SQL → insights → model → dashboard → README. Each stage was verified before starting the next.

**Q7. What was the business impact?**
It turns "customers are unhappy" into specific actions: fix the SP→RJ and North-East routes first, stop considering freight subsidies for ratings, and flag risky orders at checkout. The triage score finds 2.6x more problem orders than random, and the what-if simulator puts a number on the upside.

### B. SQL

**Q8. Why DuckDB instead of Postgres or pandas?**
DuckDB queries CSV files directly with full SQL, with no server and no load step, and it's columnar, so aggregations are fast. Postgres would need setup and a data-load step, and pandas alone wouldn't demonstrate SQL.

**Q9. Explain a window function you used.**
The Pareto cumulative share: `SUM(revenue) OVER (ORDER BY revenue DESC ROWS UNBOUNDED PRECEDING)` adds up revenue from the top-ranked row down to the current one, and dividing by `SUM(revenue) OVER ()` (the grand total) gives the cumulative percentage. Unlike `GROUP BY`, a window function keeps every row.

**Q10. What's the difference between `ROW_NUMBER`, `RANK` and `NTILE`?**
- `ROW_NUMBER` gives unique sequential numbers (I used it to keep one review per order).
- `RANK` gives tied rows the same rank and skips numbers after a tie.
- `NTILE(n)` splits rows into n roughly equal buckets (I used it for RFM quintiles).

**Q11. How did you deduplicate reviews?**
`ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC)`, keeping `rn = 1`, which is the latest review per order.

**Q12. What is a CTE and why use it?**
A Common Table Expression (`WITH name AS (...)`) is a named temporary result. It breaks a complex query into readable steps, and 16 of the 21 SQL files use one.

**Q13. How did you avoid leakage in SQL features?**
The window frame `ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING` counts only earlier orders. Any column known only after purchase (delivery dates, review) is excluded from the feature view.

**Q14. What's `LAG` / `LEAD`?**
They read a value from the previous or next row within a window. I used `LAG` for month-over-month growth and `LEAD` to find a customer's next purchase date for the repeat target.

**Q15. How did you build the funnel?**
From lifecycle timestamps: count orders with a non-null approval date, carrier date and delivery date, combined with `UNION ALL`. Then `FIRST_VALUE` gives the share of purchased orders and `LAG` gives stage-to-stage conversion.

**Q16. Why is `customer_unique_id` important?**
`customer_id` is created per order, so counting by it would treat every repeat buyer as new and hide the repeat behaviour entirely.

### C. Analytics and statistics

**Q17. What is a Pareto analysis, and what did it show?**
It ranks items by value and plots the cumulative share. Here 18 of 74 categories (24%) produce 80% of revenue, and the top 20% of sellers produce 82.3%. That's classic 80/20 concentration.

**Q18. Explain RFM and why you skipped Frequency.**
RFM segments customers by Recency, Frequency and Monetary value. 97% of customers bought exactly once, so frequency has no spread, and quintiles would split identical customers at random. I segmented on Recency × Monetary and kept frequency as a repeat flag.

**Q19. Which statistical tests did you use and why?**
- A **two-proportion z-test** comparing repeat rates (late vs on-time first order): two groups, one yes/no outcome.
- A **chi-square test** for repeat rate across three review-score groups.
- **Spearman correlation** between category freight share and low-review rate (rank-based and robust to outliers).
- An **order-weighted Pearson correlation** across states, so large states count more.

**Q20. The late-first-order effect had p = 0.093. What does that mean?**
If there were truly no difference, a gap this large or larger would appear by chance about 9% of the time. That's above the usual 5% threshold, so I report it as **not significant**. I don't claim that a bad first order reduces repeat purchases.

**Q21. What is a confounder, and how did you handle one?**
A confounder is a variable that affects both the cause and the outcome. Expensive-to-ship orders also travel further and arrive late more often, so a naive freight analysis would pick up the lateness effect. I tested freight **only on on-time orders**, which removes lateness from the comparison.

**Q22. Is late delivery really the cause of bad reviews?**
It's very plausible (the review comes after the delivery, and the effect is large and consistent), but it isn't proven, because routes, categories and sellers overlap. That's why the "avoidable" figure is labelled an upper bound, and a causal study is listed as a next step.

**Q23. What is right-censoring?**
When the outcome window is cut off by the end of the data. Recent customers look like non-returners only because time ran out. I kept only customers with a full 180-day window.

**Q24. Why are orders arriving "on the estimated day" rated worse than early ones?**
The estimates are conservative (92% of orders arrive early), so customers get used to early delivery. Arriving on the promised day already feels slow: 12.4% low reviews vs about 9% for early orders.

### D. Consulting and business

**Q25. If you had 5 minutes with the CEO, what would you say?**
"Bad reviews are mostly a delivery problem, and a regional one. Late orders are 7% of volume but a third of all bad reviews. Fix the SP→RJ and North-East routes first, stop thinking about shipping subsidies for ratings, and use our risk score to flag risky orders at checkout. Separately, 97% of customers never return. That's a CRM problem, not a delivery problem."

**Q26. How would you prioritise the recommendations?**
By impact × feasibility:
1. Route-level carrier fixes for RJ: 13.3% of revenue at 2.7x SP's late rate.
2. Proactive notifications on flagged orders: cheap to run.
3. Category delivery promises.
4. CRM for "At risk, high value" customers: 30.6% of revenue.

**Q27. Why not just subsidise freight?**
Because on on-time orders freight share moves low reviews by only 1.05 points, while lateness moves them by 53.2. Money spent on reliability buys far more satisfaction. Freight might still matter for *conversion*, but this data can't show that.

**Q28. How would you measure whether the recommendations worked?**
- An A/B test for proactive notifications on flagged orders.
- A before/after comparison with a control region for carrier changes.
- Tracking late %, low-review %, average rating and 180-day repeat rate on the Overview page.

**Q29. What's the business value of the risk model?**
Ops can review about 481 flagged orders a month (the top 10%) and catch 25.6% of future bad reviews, 2.6x more efficient than random checks. Actions include priority carrier handling, proactive messages and realistic delivery promises.

**Q30. Is revenue concentration a risk?**
Seller concentration is a key-account risk (losing a top seller hurts), but it's not an operational risk: top sellers are late 6.79% of the time vs 6.59% for the rest. So the fix is delivery routes, not the seller mix.

### E. Machine learning

**Q31. Why did you reject repeat-purchase prediction?**
Its positive rate is 3.1%, and it reached only a 1.54x PR-AUC lift, with 5.2% precision even in the top 10%. Layer 2 had already shown that first-order experience doesn't move it. A model nobody can act on isn't worth shipping.

**Q32. What is target leakage, and how did you prevent it?**
Leakage is using information during training that wouldn't be available at prediction time, which makes the model look better than it really is. I fixed the prediction time at order placement and excluded delivery dates, delay, approval time and review data. History features count only strictly earlier orders.

**Q33. Why ROC-AUC and PR-AUC together?**
ROC-AUC measures ranking quality overall but can look good on imbalanced data. PR-AUC focuses on the positive class, and its no-skill baseline equals the positive rate (0.128 here). So a PR-AUC of 0.269 means **2.10x better than chance**, which is more meaningful for a 12.8% positive class.

**Q34. Why a stratified split?**
It keeps the positive rate identical in train and test (12.81% in both), which makes metrics stable for imbalanced targets.

**Q35. Why also an out-of-time test?**
A random split leaks time-period information: the model sees orders from the bad months in training. Training on orders before May 2018 and testing after mimics real deployment. ROC-AUC dropped from 0.673 to 0.611, and I report both.

**Q36. How did you avoid overfitting?**
Early stopping on an inner validation split (never the test set), a minimum of 50 samples per leaf, row and column subsampling, L2 regularisation, and a simple baseline for comparison.

**Q37. Why LightGBM over logistic regression?**
It captures non-linear effects and interactions (e.g. category × distance) and handles categorical features natively. It improved ROC-AUC from 0.629 to 0.673 and PR-AUC from 0.232 to 0.269. Logistic regression stays as the baseline.

**Q38. Why not XGBoost or a neural network?**
XGBoost would perform similarly; LightGBM's native categorical support meant less preprocessing. A neural network is poorly suited to small tabular data like this and harder to explain.

**Q39. What does SHAP tell you, and how is it different from feature importance?**
SHAP splits each prediction into additive feature contributions (in log-odds), so it shows **direction** (raises or lowers risk) and works per order. Built-in tree importance only counts splits or gain and is biased toward high-cardinality features.

**Q40. Why is `purchase_month` the top SHAP feature? Isn't that a problem?**
It partly captures the bad periods (November 2017, February–March 2018), which a random split rewards. It's legitimately known at purchase time, and a with/without comparison during development showed it still helped slightly out of time (about +0.006 ROC-AUC). So I kept it, disclosed the effect, and reported the out-of-time score as the fair estimate.

**Q41. How would you pick a decision threshold?**
From the capacity of the ops team: if they can handle N orders a day, flag the top N by score. The triage simulator shows the trade-off (at 10% flagged: 25.6% recall, 32.8% precision).

**Q42. How would you improve the model?**
Add a second scoring point at carrier hand-off (in-transit delay), seller history features such as past late rate (computed with strictly past data), route-level historical late rates, and a time-series cross-validation scheme.

**Q43. How did you make results reproducible?**
A fixed seed, `deterministic=True` for LightGBM, `ORDER BY` in the feature query so rows arrive in a stable order, and a deterministic tie-breaker in `NTILE`. Running the notebooks twice gives identical numbers.

### F. Dashboard and engineering

**Q44. Why Streamlit and not Power BI or Tableau?**
It's free to host publicly (recruiters can click a link), pure Python, and can run what-if simulations. `docs/powerbi_notes.md` documents a full Power BI rebuild (tables, relationships, DAX measures, visuals), showing BI-tool skills too.

**Q45. How does the dashboard stay consistent with the notebooks?**
The build script runs the exact same `.sql` files and model code and saves the results as parquet. The dashboard only reads those files, so there's a single source of truth.

**Q46. Why parquet?**
It's columnar, compressed and typed. 25 files total 383 KB, so the dashboard loads instantly and deploys without the 126 MB raw data.

**Q47. How is the project portable across machines?**
`pathlib` everywhere, no absolute paths, and one `DATA_DIR` setting with an environment-variable override. Dependencies are pinned in `requirements.txt`, with a slim `dashboard/requirements.txt` for deployment.

**Q48. How did you test it?**
- The notebooks are executed headlessly (`nbconvert --execute`) and checked for errors.
- Streamlit's `AppTest` runs every page and control combination.
- The pages were checked visually in a browser.
- README numbers were cross-checked against the computed data.
- There's deliberately no heavy test suite; the focus is correctness of the analysis.

**Q49. How does the what-if simulator calculate its numbers?**
Rescued orders = late orders × slider %. They get the on-time low-review rate instead of the late rate, and the new overall rate and average rating are recomputed. It's labelled an upper bound because it assumes lateness fully causes the gap.

### G. Curveballs

**Q50. Your model's AUC is only 0.61–0.67. Isn't that weak?**
For a purchase-time score, it's reasonable: the biggest driver, actual lateness, isn't knowable yet. What matters is usefulness. The top 10% of scores contain 2.6x more bad reviews than random, which is enough to prioritise attention. I'd rather report an honest 0.611 than a leaked 0.9.

**Q51. The data is from 2018. Is any of this still relevant?**
The specific numbers are dated, but the method and the *type* of finding carry over: promise-relative lateness drives satisfaction, and retention is a separate problem. Re-running the pipeline on fresh data is a one-command job.

**Q52. How do you know the SHAP state effect isn't just revenue size?**
SHAP measures the effect on predicted risk while accounting for the other features. RJ, BA and PA come out high risk while SP (the biggest state) comes out low risk, and that matches the independent late-rate data from Layer 2.

**Q53. What if a stakeholder says freight *does* matter?**
I'd agree it may matter for *conversion*, which this data can't measure. For post-purchase satisfaction, on on-time orders the effect is 1.05 points against 53.2 for lateness, and category-level Spearman rho is −0.04 (p = 0.822). I'd propose a free-shipping-threshold A/B test to measure conversion properly.

**Q54. How would you productionise this?**
- Schedule the SQL on the live warehouse.
- Retrain monthly with an out-of-time validation gate.
- Score orders at checkout and again at carrier hand-off.
- Push flags to the ops queue.
- Monitor drift (late rates by route) and recalibrate.

---

## 15. Glossary

| Term | Meaning |
|---|---|
| **AOV** | Average order value = revenue ÷ orders |
| **Pareto / 80-20** | A small share of items produces most of the value |
| **RFM** | Recency, Frequency, Monetary customer segmentation |
| **CTE** | Common Table Expression, a `WITH` subquery with a name |
| **Window function** | A calculation across related rows that keeps every row (`OVER (...)`) |
| **Right-censoring** | The outcome is not yet observable because the data ends |
| **Confounder** | A variable that influences both the cause and the effect |
| **p-value** | The probability of a result at least this extreme if there were no real effect |
| **Target leakage** | Using information in training that isn't available at prediction time |
| **Stratified split** | A train/test split that preserves the class ratio |
| **Out-of-time test** | Train on the past, test on the future |
| **ROC-AUC** | The probability the model ranks a random positive above a random negative (0.5 = chance) |
| **PR-AUC** | Area under the precision-recall curve (chance = positive rate) |
| **Lift** | Model performance ÷ random performance |
| **Precision / recall** | Share of flagged items that are true positives / share of all positives that are flagged |
| **Early stopping** | Stop adding trees when validation performance stops improving |
| **SHAP** | Shapley-value explanation of each prediction as additive feature contributions |
| **Haversine** | Great-circle distance between two latitude/longitude points |
| **Parquet** | A columnar, compressed file format |

---

## 16. How to run it

PowerShell, from the repo root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python check_data.py                      # expect: All 9 files present

jupyter nbconvert --to notebook --execute --inplace notebooks/01_sql_analytics.ipynb
jupyter nbconvert --to notebook --execute --inplace notebooks/02_insights.ipynb
jupyter nbconvert --to notebook --execute --inplace notebooks/03_model.ipynb

python scripts/build_dashboard_data.py    # builds dashboard/data/*.parquet
streamlit run dashboard/app.py            # opens http://localhost:8501
```

The data comes from https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce. Unzip the 9 CSVs into the repo root, or set `COMMERCELENS_DATA_DIR`.
