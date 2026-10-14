"""Reproducible CommerceLens PBIP generator and independent source reconciliation."""
from pathlib import Path
import json, hashlib, uuid
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'powerbi'
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) if isinstance(value, (dict,list)) else value, encoding='utf-8')
def read(name):
    file = ROOT / (f'olist_{name}_dataset.csv' if name != 'translation' else 'product_category_name_translation.csv')
    return pd.read_csv(file)

def profile():
    o,i,p,r,c,pr,s,g,t = [read(n) for n in ['orders','order_items','order_payments','order_reviews','customers','products','sellers','geolocation','translation']]
    for col in o.columns:
        if col.endswith('_date') or col.endswith('_timestamp'): o[col] = pd.to_datetime(o[col])
    for col in ['review_creation_date','review_answer_timestamp']: r[col]=pd.to_datetime(r[col])
    latest=r.sort_values(['order_id','review_answer_timestamp','review_creation_date','review_id'],na_position='first').drop_duplicates('order_id',keep='last')
    items=i.assign(revenue=i.price+i.freight_value).groupby('order_id').agg(revenue=('revenue','sum'),item_count=('order_item_id','count'))
    f=o.merge(c[['customer_id','customer_unique_id','customer_state']],on='customer_id',validate='many_to_one').merge(items,on='order_id',how='left',validate='one_to_one').merge(latest[['order_id','review_score']],on='order_id',how='left',validate='one_to_one')
    f['delay_days']=(f.order_delivered_customer_date.dt.normalize()-f.order_estimated_delivery_date.dt.normalize()).dt.days
    f['is_late']=f.delay_days.gt(0)
    d=f[f.order_status.eq('delivered')]; eligible=d[d.delay_days.notna()]; reviewed=d[d.review_score.notna()]; cohorts=eligible[eligible.review_score.notna()]
    late=cohorts[cohorts.is_late]; ontime=cohorts[~cohorts.is_late]
    low_late=late.review_score.le(2).mean(); low_ontime=ontime.review_score.le(2).mean()
    purchase=f.order_purchase_timestamp.max().normalize()+pd.Timedelta(days=1)
    rfm=d.groupby('customer_unique_id').agg(last_purchase=('order_purchase_timestamp','max'),frequency=('order_id','size'),monetary=('revenue','sum'))
    rfm['recency']=(purchase-rfm.last_purchase.dt.normalize()).dt.days
    median=rfm.monetary.median()
    def seg(row):
        if row.recency<=90 and row.frequency>=2 and row.monetary>=median: return 'Champions'
        if row.recency<=180 and row.frequency>=2: return 'Loyal'
        if row.recency>365: return 'Lost'
        if row.recency>180: return 'At Risk'
        return 'New'
    rfm['segment']=rfm.apply(seg,axis=1)
    prod=pr.merge(t,on='product_category_name',how='left',validate='many_to_one')
    prod['category']=prod.product_category_name_english.fillna('Untranslated: '+prod.product_category_name.fillna('Unknown')).replace('Untranslated: Unknown','Unknown')
    ir=i.merge(prod[['product_id','category']],on='product_id').assign(revenue=lambda x:x.price+x.freight_value)
    cats=ir.groupby('category').revenue.sum().sort_values(ascending=False)
    metrics=dict(orders=len(f),delivered_orders=len(d),revenue=float(items.revenue.sum()),aov=float(items.revenue.sum()/len(f)),avg_rating=float(reviewed.review_score.mean()),reviewed_delivered_orders=len(reviewed),eligible_deliveries=len(eligible),late_orders=int(eligible.is_late.sum()),late_pct=float(eligible.is_late.mean()),late_reviewed=len(late),ontime_reviewed=len(ontime),late_low_count=int(late.review_score.le(2).sum()),ontime_low_count=int(ontime.review_score.le(2).sum()),low_late=float(low_late),low_ontime=float(low_ontime),gap_pp=float((low_late-low_ontime)*100),repeat_pct=float(rfm.frequency.ge(2).mean()),delivered_customers=len(rfm),repeat_customers=int(rfm.frequency.ge(2).sum()),top10_share=float(cats.head(10).sum()/cats.sum()),top_category=cats.index[0],top_category_revenue=float(cats.iloc[0]),late_avoided=float(eligible.is_late.sum()*.5),low_avoided=float(eligible.is_late.sum()*.5*(low_late-low_ontime)),projected_rating=float(reviewed.review_score.mean()+len(late)*.5*(ontime.review_score.mean()-late.review_score.mean())/len(reviewed)),rfm_asof=str(purchase.date()),rfm_median=float(median),source_review_rows=len(r),duplicate_review_rows=len(r)-len(latest),missing_reviews_delivered=int(d.review_score.isna().sum()),missing_delivery_dates=int(d.delay_days.isna().sum()),missing_categories=int(pr.product_category_name.isna().sum()),untranslated_categories=sorted(set(prod.loc[prod.product_category_name.notna() & prod.product_category_name_english.isna(),'product_category_name'])))
    checks=[dict(check='Total orders',result='PASS' if len(f)==99441 else 'FAIL',actual=len(f),expected=99441),dict(check='Low review rates: late / on-time',result='PASS' if abs(low_late-.62)<.02 and abs(low_ontime-.09)<.02 else 'FAIL',actual=[float(low_late),float(low_ontime)],expected='Approximately 62% / 9%; +/-2 percentage points'),dict(check='Delivered average review',result='PASS' if abs(metrics['avg_rating']-4.16)<.02 else 'FAIL',actual=metrics['avg_rating'],expected='4.16 +/-0.02'),dict(check='Revenue equals source price + freight',result='PASS' if abs(metrics['revenue']-float((i.price+i.freight_value).sum()))<.005 else 'FAIL',actual=metrics['revenue'],expected=float((i.price+i.freight_value).sum()))]
    key_checks={'orders_unique':not o.order_id.duplicated().any(),'customer_source_unique':not c.customer_id.duplicated().any(),'customer_dimension_unique':not c.drop_duplicates('customer_unique_id').customer_unique_id.duplicated().any(),'product_unique':not pr.product_id.duplicated().any(),'seller_unique':not s.seller_id.duplicated().any(),'order_customer_orphans':len(set(o.customer_id)-set(c.customer_id)),'item_order_orphans':len(set(i.order_id)-set(o.order_id)),'item_product_orphans':len(set(i.product_id)-set(pr.product_id)),'item_seller_orphans':len(set(i.seller_id)-set(s.seller_id))}
    checks.append(dict(check='Dimension keys and fact references',result='PASS' if all(v if isinstance(v,bool) else v==0 for v in key_checks.values()) else 'FAIL',actual=key_checks,expected='Unique keys; zero orphans'))
    write(OUT/'validation/source_results.json',dict(metrics=metrics,checks=checks,source_hashes={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in ROOT.glob('*.csv')}))
    print(json.dumps(metrics,indent=2)); return metrics,checks

if __name__=='__main__': profile()
