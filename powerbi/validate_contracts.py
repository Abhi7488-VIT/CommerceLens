"""Model structure, visual bindings, source-key and scenario endpoint checks. Not a DAX engine test."""
from pathlib import Path
import json
import pandas as pd
from build_commercelens import read,OUT
model=json.loads((OUT/'CommerceLens.SemanticModel/model.bim').read_text())['model']
tables={t['name']:t for t in model['tables']};issues=[];results=[]
def check(name,ok,detail):
    results.append(dict(check=name,result='PASS' if ok else 'FAIL',detail=detail))
    if not ok:issues.append(name)
check('Single-direction one-to-many relationships',all(r['crossFilteringBehavior']=='oneDirection' and r['fromCardinality']=='many' and r['toCardinality']=='one' for r in model['relationships']),len(model['relationships']))
for rel in model['relationships']:
    for role in ['from','to']:check('Relationship binding '+rel['name']+' '+role,rel[role+'Column'] in {x['name'] for x in tables[rel[role+'Table']]['columns']},rel[role+'Table'])
for path in (OUT/'CommerceLens.Report/definition/pages').glob('*/visuals/*/visual.json'):
    v=json.loads(path.read_text());page=json.loads(path.parents[2].joinpath('page.json').read_text());pos=v['position']
    check(str(path.relative_to(OUT))+' bounds',pos['x']>=0 and pos['y']>=0 and pos['x']+pos['width']<=page['width'] and pos['y']+pos['height']<=page['height'],'within canvas')
    check(v['name']+' accessibility','general' in v['visual']['visualContainerObjects'] and 'tabOrder' in pos,'alt text and tab order')
    for role,proj in v['visual'].get('query',{}).get('queryState',{}).items():
        for pr in proj['projections']:
            kind,expr=next(iter(pr['field'].items()));table=expr['Expression']['SourceRef']['Entity'];col=expr['Property'];names={x['name'] for x in tables[table].get('measures' if kind=='Measure' else 'columns',[])}
            check(v['name']+' '+role+' '+col,col in names,table)
o=read('orders');c=read('customers');p=read('products');s=read('sellers');i=read('order_items')
for df,key in [(o,'order_id'),(c,'customer_id'),(c.drop_duplicates('customer_unique_id'),'customer_unique_id'),(p,'product_id'),(s,'seller_id')]:check('Non-null unique '+key,not df[key].isna().any() and not df[key].duplicated().any(),len(df))
check('Unique composite order/item key',not i.duplicated(['order_id','order_item_id']).any(),len(i))
dates=pd.to_datetime(o.order_purchase_timestamp).dt.normalize();cal=pd.date_range(dates.min().replace(month=1,day=1),dates.max().replace(month=12,day=31));check('Calendar keys and fact references',not dates.isna().any() and set(dates)<=set(cal) and cal.is_unique,len(cal))
check('State keys and fact references',not c.customer_state.isna().any(),c.customer_state.nunique())
check('Customer mapping covers every fact order',set(o.customer_id)<=set(c.customer_id),len(set(o.customer_id)-set(c.customer_id)))
metrics=json.loads((OUT/'validation/source_results.json').read_text())['metrics']
for reduction in [0,.5,1]:
    avoided=metrics['late_orders']*reduction
    low=avoided*(metrics['low_late']-metrics['low_ontime'])
    rating=metrics['avg_rating']+2*reduction*(metrics['projected_rating']-metrics['avg_rating'])
    check(f'Source scenario endpoint {reduction:.0%}',0<=avoided<=metrics['late_orders'] and 1<=rating<=5 and (reduction!=0 or (avoided==0 and low==0 and rating==metrics['avg_rating'])),dict(avoided=avoided,low_reviews=low,rating=rating))
(OUT/'validation/contract_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(f'{len(results)-len(issues)} contract checks passed; {len(issues)} failed. These are source/static tests, not engine execution.')
if issues:print(issues)
raise SystemExit(bool(issues))
