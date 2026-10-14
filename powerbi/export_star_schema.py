"""Export the CommerceLens star schema to powerbi/data/ so Power Query only reads, promotes headers and types.

All cleaning rules (C01-C16) previously ran in Power Query; they now run here, once, in pandas.
Column names and types match SCHEMA in model_queries.py exactly. Usage:
    python powerbi/export_star_schema.py [RAW_CSV_FOLDER] [OUT_FOLDER]
"""
from pathlib import Path
import sys, json
import numpy as np
import pandas as pd
from model_queries import SCHEMA

ROOT = Path(__file__).resolve().parents[1]
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'powerbi' / 'data'
TS = '%Y-%m-%d %H:%M:%S'

def csv(name):
    # C01-C02: UTF-8 (BOM-tolerant) import; trim every field; empty strings become null.
    df = pd.read_csv(RAW / name, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    df = df.apply(lambda s: s.str.strip())
    return df.mask(df.eq(''))

def latest(df, by, key):
    # Deterministic "keep first after descending sort"; nulls sort last, as in Power Query.
    return df.sort_values(by, ascending=False, na_position='last', kind='mergesort').drop_duplicates(key, keep='first')

def days(a, b):
    return (a - b).dt.days.astype('Int64')

def build():
    orders_raw = csv('olist_orders_dataset.csv')
    orders_t = orders_raw.copy()
    for c in ['order_purchase_timestamp', 'order_delivered_customer_date', 'order_estimated_delivery_date']:
        orders_t[c] = pd.to_datetime(orders_t[c], format=TS)
    # C03: one row per order_id; latest purchase then customer ID wins.
    orders = latest(orders_t, ['order_purchase_timestamp', 'customer_id'], 'order_id')
    customers_raw = csv('olist_customers_dataset.csv')
    # C04: one row per transaction customer_id, resolved lexically.
    customers = customers_raw.sort_values(['customer_unique_id', 'customer_city'], kind='mergesort').drop_duplicates('customer_id')

    items_raw = csv('olist_order_items_dataset.csv')
    items_t = items_raw.assign(order_item_id=items_raw.order_item_id.astype('Int64'),
                               price=items_raw.price.astype(float), freight_value=items_raw.freight_value.astype(float))
    # C05: exact duplicate line rows removed.
    items = items_t[['order_id', 'order_item_id', 'product_id', 'seller_id', 'price', 'freight_value']].drop_duplicates()
    items = items.assign(revenue=(items.price + items.freight_value).round(2))
    item_agg = items.groupby('order_id').agg(item_revenue=('revenue', 'sum'), item_count=('revenue', 'size')).reset_index()

    pay_raw = csv('olist_order_payments_dataset.csv')
    pay_t = pay_raw.assign(payment_value=pay_raw.payment_value.astype(float), payment_sequential=pay_raw.payment_sequential.astype('Int64'))
    # C06: split tenders kept; exact duplicates removed; aggregated before joining.
    payments = pay_t.drop_duplicates()
    pay_agg = payments.groupby('order_id').agg(payment_total=('payment_value', 'sum'), payment_count=('payment_value', 'size')).reset_index()

    rev_raw = csv('olist_order_reviews_dataset.csv')
    rev_t = rev_raw.assign(review_score=rev_raw.review_score.astype('Int64'),
                           review_answer_timestamp=pd.to_datetime(rev_raw.review_answer_timestamp, format=TS),
                           review_creation_date=pd.to_datetime(rev_raw.review_creation_date, format=TS))
    # C07: latest answer, then creation, then review_id wins per order.
    reviews = latest(rev_t, ['review_answer_timestamp', 'review_creation_date', 'review_id'], 'order_id')
    reviews = reviews.assign(review_score=reviews.review_score.where(reviews.review_score.between(1, 5)))

    f = orders.merge(customers[['customer_id', 'customer_unique_id', 'customer_state', 'customer_city']]
                     .rename(columns={'customer_state': 'state', 'customer_city': 'city'}), on='customer_id', how='left', validate='many_to_one')
    f = f.merge(item_agg, on='order_id', how='left', validate='one_to_one')
    f = f.merge(pay_agg, on='order_id', how='left', validate='one_to_one')
    f = f.merge(reviews[['order_id', 'review_score']], on='order_id', how='left', validate='one_to_one')
    # C08: no item rows -> zero revenue/count; missing payment stays null.
    f['item_revenue'] = f.item_revenue.fillna(0).round(2)
    f['item_count'] = f.item_count.fillna(0).astype('Int64')
    f['payment_total'] = f.payment_total.round(2)
    f['payment_count'] = f.payment_count.astype('Int64')
    # C09: calendar-day comparisons.
    f['purchase_date'] = f.order_purchase_timestamp.dt.normalize()
    f['delivered_date'] = f.order_delivered_customer_date.dt.normalize()
    f['estimated_date'] = f.order_estimated_delivery_date.dt.normalize()
    f['delivery_days'] = days(f.delivered_date, f.purchase_date)
    f['estimated_days'] = days(f.estimated_date, f.purchase_date)
    f['delay_days'] = days(f.delivered_date, f.estimated_date)
    f['is_late'] = (f.delay_days > 0).astype('boolean').where(f.delay_days.notna())
    f['is_low_review'] = (f.review_score <= 2).astype('boolean').where(f.review_score.notna())
    f['delivery_group'] = np.where(f.is_late.isna(), 'Unknown', np.where(f.is_late.fillna(False).astype(bool), 'Late', 'On-time'))
    # C10: five-day bins (floor), negatives = early.
    f['delay_bin'] = (f.delay_days // 5) * 5
    fact_orders = f[[c for c, _ in SCHEMA['fact_orders']]]

    # C11: person-grain customer; latest observed order's address.
    base = latest(f, ['order_purchase_timestamp', 'order_id'], 'customer_unique_id')[['customer_unique_id', 'city', 'state']]
    delivered = fact_orders[fact_orders.order_status == 'delivered']
    # C12: fixed RFM snapshot, as of one day after the last purchase.
    as_of = fact_orders.purchase_date.max() + pd.Timedelta(days=1)
    rfm = delivered.groupby('customer_unique_id').agg(last=('purchase_date', 'max'), frequency=('order_id', 'size'), monetary=('item_revenue', 'sum')).reset_index()
    rfm['recency'] = (as_of - rfm['last']).dt.days
    rfm['monetary'] = rfm.monetary.round(2)
    median = rfm.monetary.median()
    cust = base.merge(rfm[['customer_unique_id', 'recency', 'frequency', 'monetary']], on='customer_unique_id', how='left', validate='one_to_one')
    cust['frequency'] = cust.frequency.fillna(0).astype('Int64')
    cust['monetary'] = cust.monetary.fillna(0)
    cust['recency'] = cust.recency.astype('Int64')
    def seg(r):
        if r.frequency == 0: return 'New'
        if r.recency <= 90 and r.frequency >= 2 and r.monetary >= median: return 'Champions'
        if r.recency <= 180 and r.frequency >= 2: return 'Loyal'
        if r.recency > 365: return 'Lost'
        if r.recency > 180: return 'At Risk'
        return 'New'
    cust['rfm_segment'] = cust.apply(seg, axis=1)
    dim_customer = cust[[c for c, _ in SCHEMA['dim_customer']]]

    prod_raw = csv('olist_products_dataset.csv')
    products = prod_raw[['product_id', 'product_category_name']].drop_duplicates('product_id')
    trans = csv('product_category_name_translation.csv').drop_duplicates('product_category_name')
    pj = products.merge(trans, on='product_category_name', how='left', validate='many_to_one')
    # C13: missing -> Unknown; untranslated keeps its original name with a label.
    pj['category'] = np.where(pj.product_category_name.isna(), 'Unknown',
                              np.where(pj.product_category_name_english.isna(), 'Untranslated: ' + pj.product_category_name.fillna(''), pj.product_category_name_english))
    dim_product = pj[['product_id', 'category']]

    dim_seller = csv('olist_sellers_dataset.csv')[['seller_id', 'seller_city', 'seller_state']].drop_duplicates('seller_id')

    geo_raw = csv('olist_geolocation_dataset.csv')
    geo = geo_raw[['geolocation_state', 'geolocation_zip_code_prefix', 'geolocation_lat', 'geolocation_lng']].astype(
        {'geolocation_lat': float, 'geolocation_lng': float}).drop_duplicates()
    # C14: duplicate/invalid points excluded; geolocation is only used for one centroid per state.
    geo = geo[geo.geolocation_lat.between(-90, 90) & geo.geolocation_lng.between(-180, 180)]
    centroids = geo.groupby('geolocation_state').agg(latitude=('geolocation_lat', 'mean'), longitude=('geolocation_lng', 'mean')).reset_index()
    states = fact_orders[['state']].drop_duplicates()
    dim_state = states.merge(centroids, left_on='state', right_on='geolocation_state', how='left', validate='one_to_one')
    dim_state = dim_state.assign(country='Brazil')[[c for c, _ in SCHEMA['dim_state']]]

    # C15: continuous full calendar years; week = Date.WeekOfYear(d, Day.Monday).
    dates = pd.date_range(fact_orders.purchase_date.min().replace(month=1, day=1), fact_orders.purchase_date.max().replace(month=12, day=31), freq='D')
    jan1_wd = pd.to_datetime(dates.year.astype(str) + '-01-01').weekday
    dim_date = pd.DataFrame({'Date': dates, 'year': dates.year, 'quarter': 'Q' + dates.quarter.astype(str), 'month': dates.month,
                             'month_name': dates.month_name(), 'week': (dates.dayofyear - 1 + jan1_wd) // 7 + 1, 'year_month': dates.strftime('%Y-%m')})

    n = len
    cleaning_log = pd.DataFrame([
        ('C01-C02', 'UTF-8; trim strings; empty strings to null', n(orders_raw)),
        ('C03', 'Duplicate order IDs removed', n(orders_raw) - n(orders)),
        ('C04', 'Duplicate transaction customer IDs removed', n(customers_raw) - n(customers)),
        ('C05', 'Exact duplicate item rows removed', n(items_raw) - n(items)),
        ('C06', 'Exact duplicate payment rows removed; split tenders retained', n(pay_raw) - n(payments)),
        ('C07', 'Superseded review rows removed', n(rev_raw) - n(reviews)),
        ('C08', 'Orders with no item rows; revenue set to zero', int((fact_orders.item_count == 0).sum())),
        ('C09', 'Delivered orders with missing delay; excluded from lateness denominator', int(delivered.delay_days.isna().sum())),
        ('C10', 'Five-day bins; early deliveries retained', n(fact_orders)),
        ('C11', 'Multiple transaction addresses consolidated to person dimension', n(customers) - n(dim_customer)),
        ('C12', f'RFM as of {as_of:%Y-%m-%d}; median monetary {median:.15g}', n(rfm)),
        ('C13', 'Products with missing English translation or category', int(pj.product_category_name_english.isna().sum())),
        ('C14', 'Geolocation duplicate or invalid points excluded', n(geo_raw) - n(geo)),
        ('C15', 'Continuous full-year calendar', n(dim_date)),
        ('C16', 'Delivered orders with no valid review; excluded from review denominators', int(delivered.review_score.isna().sum())),
    ], columns=['step', 'detail', 'affected_rows'])

    m = rfm.monetary.sort_values().to_numpy(); mid = len(m) // 2
    notes = {'median_monetary': float(median), 'rfm_rows': len(m),
             'median_middle_values_equal': bool(len(m) % 2 == 1 or m[mid - 1] == m[mid])}
    return dict(fact_orders=fact_orders, fact_order_items=items[[c for c, _ in SCHEMA['fact_order_items']]], dim_customer=dim_customer,
                dim_product=dim_product, dim_seller=dim_seller, dim_state=dim_state, dim_date=dim_date, cleaning_log=cleaning_log), notes

KEYS = {'fact_orders': ['order_id'], 'fact_order_items': ['order_id', 'order_item_id'], 'dim_customer': ['customer_unique_id'],
        'dim_product': ['product_id'], 'dim_seller': ['seller_id'], 'dim_state': ['state'], 'dim_date': ['Date']}

def validate(tables):
    problems = []
    for name, cols in SCHEMA.items():
        got = list(tables[name].columns)
        if got != [c for c, _ in cols]: problems.append(f'{name}: columns {got} do not match model')
    for name, key in KEYS.items():
        df = tables[name]
        k = df[key].astype(str).apply(lambda s: s.str.lower())  # Vertipaq keys are case-insensitive
        if df[key].isna().any().any(): problems.append(f'{name}: null key')
        if k.duplicated().any(): problems.append(f'{name}: {int(k.duplicated().sum())} duplicate keys on {key}')
    fo, fi = tables['fact_orders'], tables['fact_order_items']
    for col, dim, dcol in [('customer_unique_id', 'dim_customer', 'customer_unique_id'), ('state', 'dim_state', 'state')]:
        orphans = int((~fo[col].isin(tables[dim][dcol])).sum())
        if orphans: problems.append(f'fact_orders.{col}: {orphans} rows with no {dim} match')
    if not fo.purchase_date.isin(tables['dim_date'].Date).all(): problems.append('fact_orders.purchase_date outside dim_date')
    for col, dim in [('order_id', 'fact_orders'), ('product_id', 'dim_product'), ('seller_id', 'dim_seller')]:
        orphans = int((~fi[col].isin(tables[dim][col])).sum())
        if orphans: problems.append(f'fact_order_items.{col}: {orphans} rows with no {dim} match')
    return problems

def write(tables):
    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        types = dict(SCHEMA.get(name, [('step', 'string'), ('detail', 'string'), ('affected_rows', 'int64')]))
        out = df.copy()
        for c, t in types.items():
            if t == 'dateTime': out[c] = out[c].dt.strftime('%Y-%m-%d')
            elif t == 'boolean': out[c] = out[c].map({True: 'true', False: 'false'}).fillna('')
            elif t == 'decimal': out[c] = out[c].round(2)
        out.to_csv(OUT / f'{name}.csv', index=False, encoding='utf-8', lineterminator='\n')

if __name__ == '__main__':
    tables, notes = build()
    problems = validate(tables)
    write(tables)
    null_text = {n: [c for c, t in SCHEMA.get(n, []) if t == 'string' and tables[n][c].isna().any()] for n in SCHEMA}
    print(json.dumps({'out': str(OUT), 'rows': {n: len(df) for n, df in tables.items()},
                      'text_columns_with_nulls': {k: v for k, v in null_text.items() if v}, 'notes': notes, 'problems': problems}, indent=2))
    sys.exit(bool(problems))
