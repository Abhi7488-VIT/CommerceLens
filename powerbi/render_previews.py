"""Source-data previews, explicitly not Power BI screenshots or proof of report rendering."""
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from build_commercelens import read,ROOT,OUT
N='#15354B';T='#087F8C';G='#E6B422';BG='#F2F4F5';TXT='#203440';MUT='#526572'
plt.rcParams.update({'font.family':'Segoe UI','font.size':11,'text.color':TXT,'axes.labelcolor':MUT,'xtick.color':MUT,'ytick.color':MUT,'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False,'axes.spines.bottom':False})
o=read('orders');i=read('order_items');c=read('customers');r=read('order_reviews');p=read('products');tr=read('translation');s=read('sellers')
o['purchase_date']=pd.to_datetime(o.order_purchase_timestamp).dt.normalize()
o['delay']=(pd.to_datetime(o.order_delivered_customer_date).dt.normalize()-pd.to_datetime(o.order_estimated_delivery_date).dt.normalize()).dt.days
r=r.sort_values(['review_answer_timestamp','review_creation_date','review_id'],na_position='first').drop_duplicates('order_id',keep='last')
i['revenue']=i.price+i.freight_value
f=o.merge(c,on='customer_id').merge(r[['order_id','review_score']],on='order_id',how='left').merge(i.groupby('order_id').revenue.sum(),on='order_id',how='left')
f['revenue']=f.revenue.fillna(0)
d=f[f.order_status.eq('delivered')].copy();d['delivery_group']=d.delay.map(lambda x:'Unknown' if pd.isna(x) else ('Late' if x>0 else 'On-time'))
m=json.loads((OUT/'validation/source_results.json').read_text())['metrics']
def page(title,num):
    fig=plt.figure(figsize=(19.2,10.8),dpi=100,facecolor=BG)
    fig.text(.035,.948,'COMMERCE LENS',fontsize=25,fontweight='bold',color=N)
    fig.text(.035,.912,f'REVENUE & RETENTION ANALYTICS  /  {num:02d}  {title.upper()}',fontsize=11,color=MUT)
    for j,x in enumerate(['Overview','Delivery & reviews','Scenario','Customers']):
        left=.55+j*.103;fig.patches.append(Rectangle((left,.936),.098,.036,transform=fig.transFigure,facecolor=T if j==num-1 else N))
        fig.text(left+.049,.954,x,ha='center',va='center',fontsize=10,color='white')
    for x,w,t in [(.035,.245,'Purchase date   ·   Sep 2016 – Oct 2018'),(.295,.195,'State   ·   All'),(.505,.275,'Product category   ·   All'),(.795,.17,'Order status   ·   All')]:
        fig.patches.append(Rectangle((x,.837),w,.051,transform=fig.transFigure,facecolor='white'))
        fig.text(x+.012,.862,t,va='center',fontsize=11)
    fig.text(.035,.026,'OLIST BRAZIL  |  Historical snapshot  •  Revenue includes freight  •  Delivery / review metrics: delivered only',fontsize=10,color=MUT)
    fig.text(.965,.026,'DATA-VERIFIED PREVIEW · DESKTOP RENDER PENDING',ha='right',fontsize=9,color=MUT)
    return fig
def card(fig,x,y,w,h,title,value):
    fig.patches.append(Rectangle((x,y),w,h,transform=fig.transFigure,facecolor='white',zorder=0))
    fig.text(x+.015,y+h-.035,title,fontsize=11,color=MUT)
    fig.text(x+.015,y+.032,value,fontsize=30,color=N,fontweight='bold')
def ax(fig,rect,title):
    a=fig.add_axes(rect,facecolor='white');a.set_title(title,loc='left',fontsize=13,fontweight='bold',pad=18);a.tick_params(length=0);return a
def note(fig,t,y=.085):fig.text(.05,y,t,fontsize=15,color=N)
def save(fig,name):
    dest=OUT/'previews';dest.mkdir(exist_ok=True);fig.savefig(dest/name,facecolor=fig.get_facecolor());plt.close(fig)

fig=page('Executive Summary',1)
for j,(title,value) in enumerate([('Gross revenue',f'R${m["revenue"]/1e6:.2f}m'),('Orders • all statuses',f'{m["orders"]:,}'),('Average order value',f'R${m["aov"]:.2f}'),('Delivered rating',f'{m["avg_rating"]:.2f} / 5'),('Late delivery share',f'{100*m["late_pct"]:.2f}%')]):card(fig,.035+j*.188,.665,.178,.14,title,value)
monthly=f.groupby(f.purchase_date.dt.to_period('M')).revenue.sum();months=pd.period_range(monthly.index.min(),monthly.index.max(),freq='M');monthly=monthly.reindex(months,fill_value=0)
a=ax(fig,[.06,.25,.48,.33],'Monthly gross revenue | month-on-month change in report tooltip')
a.plot(range(len(monthly)),monthly/1e6,color=T,lw=3,marker='o',markersize=4);a.fill_between(range(len(monthly)),monthly/1e6,color=T,alpha=.07);a.set_ylabel('Revenue · R$ million');a.set_xticks(range(0,len(monthly),3),[str(x) for x in monthly.index[::3]],rotation=30,ha='right')
a.text(.02,.94,'Edge months are incomplete; startup MoM rates have small bases.',transform=a.transAxes,fontsize=10,color=MUT)
prod=p.merge(tr,on='product_category_name',how='left');prod['category']=prod.product_category_name_english.fillna('Untranslated: '+prod.product_category_name.fillna('Unknown')).replace('Untranslated: Unknown','Unknown')
cats=i.merge(prod[['product_id','category']],on='product_id').groupby('category').revenue.sum().nlargest(10).sort_values()
a=ax(fig,[.72,.25,.23,.33],'Ten categories lead the revenue mix')
a.barh(cats.index.str.replace('_',' '),cats/1e6,color=N);a.set_xlabel('Revenue · R$ million');a.tick_params(axis='y',labelsize=10)
note(fig,f'Top ten categories generate {m["top10_share"]:.1%} of gross sales. Focus reliability improvements where revenue is concentrated.')
save(fig,'01_executive_summary.png')

fig=page('Delivery & Reviews',2)
note(fig,f'Late orders receive 1–2 star reviews {m["low_late"]:.1%} of the time vs {m["low_ontime"]:.1%} on-time.',.78)
valid=d[d.delivery_group.ne('Unknown') & d.review_score.notna()]
dist=pd.crosstab(valid.delivery_group,valid.review_score,normalize='index').reindex(['Late','On-time'])
a=ax(fig,[.06,.47,.25,.23],'Review mix shifts sharply with lateness');bottom=[0.,0.]
for score,col in zip(range(1,6),[N,'#496476','#8CA2AE',T,G]):
    vals=dist[score].values*100;a.bar(['Late','On-time'],vals,bottom=bottom,label=f'{score} star',color=col,width=.5);bottom+=vals
a.set_ylim(0,100);a.set_ylabel('% reviewed orders');a.legend(ncol=5,fontsize=9,loc='upper center',bbox_to_anchor=(.5,-.12),frameon=False)
a=ax(fig,[.39,.49,.22,.21],'Low reviews | 1–2 stars');a.barh(['On-time','Late'],[100*m['low_ontime'],100*m['low_late']],color=[T,N]);a.set_xlim(0,80)
for y,v in enumerate([100*m['low_ontime'],100*m['low_late']]):a.text(v+1,y,f'{v:.2f}%',va='center')
geo=read('geolocation').drop_duplicates(['geolocation_state','geolocation_zip_code_prefix','geolocation_lat','geolocation_lng']);geo=geo.groupby('geolocation_state')[['geolocation_lat','geolocation_lng']].mean()
st=d[d.delay.notna()].assign(late=lambda x:x.delay.gt(0)).groupby('customer_state').late.agg(['mean','size']).join(geo)
a=ax(fig,[.71,.46,.24,.25],'State exposure | geographic bubble view');a.scatter(st.geolocation_lng,st.geolocation_lat,s=st['mean']*1800,color=T,alpha=.7,edgecolors=N)
for name,row in st.iterrows():a.annotate(name,(row.geolocation_lng,row.geolocation_lat),xytext=(3,3),textcoords='offset points',fontsize=8)
a.set_xlabel('Longitude');a.set_ylabel('Latitude');a.text(.98,.02,'Bubble size = late %',transform=a.transAxes,ha='right',fontsize=9)
a=ax(fig,[.06,.15,.49,.22],'Delivery timing | five-day bins; negative = early');bins=(d.delay.dropna()//5*5).value_counts().sort_index();a.bar(bins.index,bins.values,width=4.5,color=T);a.axvline(0,color=N,lw=1);a.set_xlabel('Days after promised date');a.set_ylabel('Delivered orders')
a=ax(fig,[.65,.15,.30,.22],'Low-review decomposition | starting branches');a.axis('off')
a.text(.02,.53,f'All reviewed delivered\n{d.review_score.dropna().le(2).mean():.2%} low reviews',bbox=dict(facecolor=BG,edgecolor='none',pad=12),fontsize=12)
for y,label,val in [(.75,'Late',m['low_late']),(.16,'On-time',m['low_ontime'])]:
    a.annotate('',xy=(.56,y+.05),xytext=(.39,.56),arrowprops=dict(arrowstyle='-',color=MUT));a.text(.60,y,f'{label}\n{val:.2%}',fontsize=15,color=N)
a.text(.02,-.12,'Native report adds interactive state and category expansion.',fontsize=9,color=MUT)
save(fig,'02_delivery_reviews.png')

fig=page('Scenario Simulator',3)
note(fig,'Illustrative scenario: halve late deliveries; estimate the change using observed cohort differences.',.78)
a=fig.add_axes([.06,.665,.88,.07],facecolor='white');a.plot([0,1],[.5,.5],color='#ABC0C8',lw=8);a.plot([0,.5],[.5,.5],color=T,lw=8);a.scatter([.5],[.5],s=220,color=N,zorder=5);a.set_xlim(-.02,1.02);a.set_ylim(0,1);a.set_yticks([]);a.set_xticks([0,.25,.5,.75,1],['0%','25%','50%','75%','100%']);a.set_title('Late reduction parameter · 50% selected',loc='left',fontsize=13,fontweight='bold')
for j,(title,value) in enumerate([('Late orders avoided • expected',f'{m["late_avoided"]:,.0f}'),('Low reviews avoided • estimated',f'{m["low_avoided"]:,.0f}'),('Projected average rating',f'{m["projected_rating"]:.2f} / 5')]):card(fig,.035+j*.314,.465,.299,.14,title,value)
a=ax(fig,[.08,.17,.36,.22],'Rating projection | full 0–5 scale');vals=[m['avg_rating'],m['projected_rating']];a.bar(['Before','After'],vals,color=[N,T],width=.4);a.set_ylim(0,5)
for j,v in enumerate(vals):a.text(j,v+.1,f'{v:.3f}',ha='center')
a=ax(fig,[.60,.17,.35,.22],'Late-order volume | before and after');vals=[m['late_orders'],m['late_orders']-m['late_avoided']];a.barh(['Before','After'],vals,color=[N,T],height=.45);a.set_xlim(0,8000)
for j,v in enumerate(vals):a.text(v+100,j,f'{v:,.0f}',va='center')
note(fig,'Association, not causation. Assumes comparable cohorts and unchanged review propensity.',.075)
save(fig,'03_scenario_simulator.png')

fig=page('Customers & Geography',4)
note(fig,f'Only {m["repeat_pct"]:.1%} of delivered customers purchased again within this observation window.',.78)
rfm=d.groupby('customer_unique_id').agg(last=('purchase_date','max'),frequency=('order_id','size'),monetary=('revenue','sum'));rfm['recency']=(pd.Timestamp(m['rfm_asof'])-rfm['last']).dt.days
def segment(x):
    if x.recency<=90 and x.frequency>=2 and x.monetary>=m['rfm_median']:return 'Champions'
    if x.recency<=180 and x.frequency>=2:return 'Loyal'
    if x.recency>365:return 'Lost'
    if x.recency>180:return 'At Risk'
    return 'New'
counts=rfm.apply(segment,axis=1).value_counts().reindex(['Champions','Loyal','At Risk','Lost','New'],fill_value=0)
a=ax(fig,[.055,.46,.27,.25],'Five segments guide customer outreach');wedges,_=a.pie(counts,colors=[T,G,N,'#627988','#ABC0C8'],startangle=90,wedgeprops=dict(width=.32,edgecolor='white'));a.legend(wedges,counts.index,loc='center left',bbox_to_anchor=(.88,.5),frameon=False,fontsize=10)
strev=f.groupby('customer_state').revenue.sum().nlargest(8).sort_values();a=ax(fig,[.48,.47,.23,.24],'Largest markets | revenue by state');a.barh(strev.index,strev/1e6,color=T);a.set_xlabel('R$ million')
card(fig,.76,.59,.205,.13,'Repeat purchase rate',f'{m["repeat_pct"]:.2%}');card(fig,.76,.435,.205,.13,'Delivered customers',f'{m["delivered_customers"]:,}')
a=ax(fig,[.105,.14,.27,.22],'Customer count by RFM segment');a.barh(counts.index,counts,color=N)
for j,v in enumerate(counts):a.text(v+400,j,f'{v:,}',va='center',fontsize=10)
a.set_xlim(0,counts.max()*1.22)
top=i.groupby('seller_id').revenue.sum().nlargest(5).reset_index().merge(s[['seller_id','seller_state']],on='seller_id');a=ax(fig,[.49,.14,.46,.22],'Top seller contribution | revenue includes freight');a.axis('off')
rows=[[x.seller_id[:12]+'…',x.seller_state,f'R${x.revenue:,.2f}'] for x in top.itertuples()]
tbl=a.table(cellText=rows,colLabels=['Seller ID (abbreviated)','State','Gross revenue'],loc='center',cellLoc='left',colLoc='left',colWidths=[.48,.15,.37]);tbl.auto_set_font_size(False);tbl.set_fontsize(11);tbl.scale(1,2.1)
for (rr,cc),cell in tbl.get_celld().items():cell.set_edgecolor(BG);cell.set_facecolor(N if rr==0 else ('white' if rr%2 else BG));cell.get_text().set_color('white' if rr==0 else TXT)
save(fig,'04_customers_geography.png')
(OUT/'previews/README.md').write_text('These four PNGs are source-data-derived design previews rendered with Matplotlib. They are NOT Power BI Desktop screenshots. Desktop refresh, visual rendering, maps and interactions remain to be verified. All plotted figures are calculated from the supplied CSVs.\n',encoding='utf-8')
print('Four labeled data-derived PNG previews written; not Desktop screenshots.')
