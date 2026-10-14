"""Generate native PBIR visuals; no raster charts or hard-coded KPI values."""
from pathlib import Path
import json
from build_model import write,OUT
R=OUT/'CommerceLens.Report'; D=R/'definition'
BASE='https://developer.microsoft.com/json-schemas/fabric/item/report/'
NAVY='#15354B'; TEAL='#087F8C'; GOLD='#E6B422'; BG='#F2F4F5'; INK='#203440'; GRAY='#526572'
def lit(v):
    if isinstance(v,bool):s=str(v).lower()
    elif isinstance(v,(int,float)):s=str(v)+'D'
    else:s="'"+v.replace("'","''")+"'"
    return {'expr':{'Literal':{'Value':s}}}
def color(v):return {'solid':{'color':lit(v)}}
def props(**kw):return [{'properties':kw}]
def field(t,c,measure=False):return {('Measure' if measure else 'Column'):{'Expression':{'SourceRef':{'Entity':t}},'Property':c}}
def f(t,c):return (t,c,False)
def m(c):return ('fact_orders',c,True)
def projection(a):return dict(field=field(*a),queryRef=a[0]+'.'+a[1],nativeQueryRef=a[1])
PAGES=[('Executive','Executive Summary'),('Delivery','Delivery & Reviews'),('Scenario','Scenario Simulator'),('Customers','Customers & Geography')]
VIS={}; PAGE={}
def visual(page,name,typ,x,y,w,h,title='',roles=None,objects=None):
    seq=len(VIS.setdefault(page,[]))
    v={'$schema':BASE+'definition/visualContainer/2.1.0/schema.json','name':name,'position':dict(x=x,y=y,z=seq,width=w,height=h,tabOrder=seq),'visual':{'visualType':typ,'drillFilterOtherVisuals':True,'visualContainerObjects':{
      'title':props(show=lit(bool(title)),text=lit(title),fontColor=color(INK),fontSize=lit(12),fontFamily=lit('Segoe UI'),bold=lit(True)),
      'background':props(show=lit(True),color=color('#FFFFFF'),transparency=lit(0)),
      'border':props(show=lit(False)),
      'visualHeader':props(show=lit(False)),
      'general':props(altText=lit(title or name))}}}
    if roles:v['visual']['query']={'queryState':{role:{'projections':[projection(a) for a in args]} for role,args in roles.items()}}
    if objects:v['visual']['objects']=objects
    VIS[page].append(v);return v
def text(page,name,value,x,y,w,h,size=14,fg=INK,bg=BG):
    v=visual(page,name,'textbox',x,y,w,h,objects={'general':props(paragraphs=[{'textRuns':[{'value':value,'textStyle':{'fontFamily':'Segoe UI','fontSize':f'{size}pt','color':fg}}]}])})
    v['visual']['visualContainerObjects']['background']=props(show=lit(True),color=color(bg),transparency=lit(0))
    return v
def card(page,name,measure,x,y,w,h,label,large=28):
    return visual(page,name,'card',x,y,w,h,label,{'Values':[m(measure)]},{'labels':props(color=color(NAVY),fontSize=lit(large),fontFamily=lit('Segoe UI')),'categoryLabels':props(show=lit(False))})
def button(page,name,label,target,x,w=138,bookmark=False):
    v=visual(page,name,'actionButton',x,26,w,30,objects={'text':props(show=lit(True),text=lit(label),fontColor=color('#FFFFFF'),fontSize=lit(10),fontFamily=lit('Segoe UI')),'icon':props(show=lit(False)),'fill':props(show=lit(True),fillColor=color(NAVY),transparency=lit(0)),'outline':props(show=lit(False))})
    v['visual']['visualContainerObjects']['visualLink']=props(show=lit(True),type=lit('Bookmark' if bookmark else 'PageNavigation'),**{('bookmark' if bookmark else 'navigationSection'):lit(target)})
    return v
def categorical_filter(t,c,value):
    return {'Version':2,'From':[{'Name':'s','Entity':t,'Type':0}],'Where':[{'Condition':{'In':{'Expressions':[{'Column':{'Expression':{'SourceRef':{'Source':'s'}},'Property':c}}],'Values':[[{'Literal':{'Value':("'"+value+"'") if isinstance(value,str) else str(value)+'D'}}]]}}}]}
def slicer(page,name,t,c,x,w,label):
    v=visual(page,name,'slicer',x,92,w,58,label,{'Values':[f(t,c)]},{'data':props(mode=lit('Dropdown')),'header':props(show=lit(False)),'selection':props(selectAllCheckboxEnabled=lit(True)),'items':props(fontColor=color(INK),textSize=lit(10))})
    v['visual']['syncGroup']={'groupName':name,'fieldChanges':True,'filterChanges':True}
    return v
def page(name,label,hidden=False,w=1280,h=720):
    p={'$schema':BASE+'definition/page/1.0.0/schema.json','name':name,'displayName':label,'displayOption':'FitToPage','height':h,'width':w,'objects':{'background':props(color=color(BG),transparency=lit(0))}}
    if hidden:p['visibility']='HiddenInViewMode'
    PAGE[name]=p;VIS[name]=[]
def chrome(name,label,idx):
    page(name,label)
    text(name,'Brand','COMMERCE LENS',28,22,280,38,22,NAVY)
    for k,(dest,lab) in enumerate(PAGES):button(name,'nav_'+dest,['Overview','Delivery & reviews','Scenario','Customers'][k],dest,570+k*148,140)
    button(name,'Reset','Reset filters','Reset',1168,90,True)
    text(name,'Subtitle',f'REVENUE & RETENTION ANALYTICS  /  {idx:02d}  {label.upper()}',30,61,1000,24,10,GRAY)
    slicer(name,'sync_date','dim_date','Date',28,330,'Purchase date')
    VIS[name][-1]['visual']['objects']['data']=props(mode=lit('Between'))
    slicer(name,'sync_state','dim_state','state',374,220,'Customer state')
    slicer(name,'sync_category','dim_product','category',610,370,'Product category')
    slicer(name,'sync_status','fact_orders','order_status',996,256,'Order status')
    text(name,'Footer','OLIST BRAZIL  |  2016–2018 historical snapshot  •  R$ includes item price + freight  •  Delivery / review KPIs: delivered only',28,690,1224,22,9,GRAY)
def labels():return {'labels':props(show=lit(True),color=color(INK),fontSize=lit(10)),'categoryAxis':props(labelColor=color(GRAY),fontSize=lit(10),showAxisTitle=lit(False)),'valueAxis':props(labelColor=color(GRAY),fontSize=lit(10),showAxisTitle=lit(False)),'legend':props(show=lit(True),position=lit('Top'),labelColor=color(INK))}
def tooltip(v):v['visual']['visualContainerObjects']['visualTooltip']=props(show=lit(True),type=lit('ReportPage'),section=lit('Tooltip'))
def build():
    theme={'name':'CommerceLens Consulting','dataColors':[NAVY,TEAL,GOLD,'#627988','#ABC0C8'],'background':'#FFFFFF','foreground':INK,'tableAccent':TEAL,'good':TEAL,'neutral':GOLD,'bad':NAVY,'textClasses':{'title':{'fontFace':'Segoe UI','fontSize':14,'color':INK},'label':{'fontFace':'Segoe UI','fontSize':11,'color':GRAY},'callout':{'fontFace':'Segoe UI','fontSize':30,'color':NAVY},'header':{'fontFace':'Segoe UI','fontSize':12,'color':INK}},'visualStyles':{'*':{'*':{'title':[{'fontFamily':'Segoe UI','fontSize':12,'color':{'solid':{'color':INK}}}],'background':[{'color':{'solid':{'color':'#FFFFFF'}},'transparency':0}],'border':[{'show':False}]}}}}
    write(OUT/'theme.json',theme);write(R/'StaticResources/RegisteredResources/CommerceLens.json',theme)
    write(R/'definition.pbir',{'$schema':BASE+'definitionProperties/2.0.0/schema.json','version':'4.0','datasetReference':{'byPath':{'path':'../CommerceLens.SemanticModel'}}})
    write(D/'version.json',{'$schema':BASE+'definition/versionMetadata/1.0.0/schema.json','version':'2.0.0'})
    write(D/'report.json',{'$schema':BASE+'definition/report/3.1.0/schema.json','themeCollection':{'customTheme':{'name':'CommerceLens','reportVersionAtImport':{'visual':'2.1.0','report':'3.1.0','page':'1.0.0'},'type':'RegisteredResources'}},'resourcePackages':[{'name':'RegisteredResources','type':'RegisteredResources','items':[{'name':'CommerceLens','path':'CommerceLens.json','type':'CustomTheme'}]}],'settings':{'useStylableVisualContainerHeader':True,'exportDataMode':'AllowSummarized','defaultDrillFilterOtherVisuals':True}})
    for idx,(n,l) in enumerate(PAGES,1):chrome(n,l,idx)
    for j,(meas,label) in enumerate([('Total Revenue','Gross revenue • R$'),('Orders','Orders • all statuses'),('AOV','Average order value'),('Avg Review Score','Delivered rating • /5'),('Late Delivery %','Delivered late share')]):card('Executive',f'KPI{j}',meas,28+j*248,170,232,110,label)
    v=visual('Executive','RevenueTrend','lineChart',28,300,700,310,'Monthly gross revenue | hover for month-on-month change',{'Category':[f('dim_date','year_month')],'Y':[m('Total Revenue')],'Tooltips':[m('Revenue MoM %')]},labels());tooltip(v)
    visual('Executive','TopCategories','clusteredBarChart',748,300,504,310,'Ten categories with the largest revenue contribution',{'Category':[f('dim_product','category')],'Y':[m('Top 10 Category Revenue')]},labels())
    card('Executive','Insight','Executive Insight',28,627,1224,51,'',15)
    card('Delivery','Insight','Delivery Insight',28,166,1224,58,'',17)
    v=visual('Delivery','ReviewDistribution','hundredPercentStackedColumnChart',28,240,390,200,'Late deliveries shift the review mix toward 1–2 stars',{'Category':[f('fact_orders','delivery_group')],'Series':[f('fact_orders','review_score')],'Y':[m('Delivered Reviewed Orders')]},labels())
    v['filterConfig']={'filters':[{'name':'DeliveryGroups','field':field('fact_orders','delivery_group'),'type':'Categorical','filter':{'Version':2,'From':[{'Name':'s','Entity':'fact_orders','Type':0}],'Where':[{'Condition':{'In':{'Expressions':[{'Column':{'Expression':{'SourceRef':{'Source':'s'}},'Property':'delivery_group'}}],'Values':[[{'Literal':{'Value':"'Late'"}}],[{'Literal':{'Value':"'On-time'"}}]]}}}]}}]}
    v=visual('Delivery','LowReviewCompare','clusteredBarChart',438,240,390,200,'Compare the share of 1–2 star reviews',{'Category':[f('fact_orders','delivery_group')],'Y':[m('Low Review %')]},labels());v['filterConfig']=VIS['Delivery'][-2]['filterConfig']
    v=visual('Delivery','StateMap','map',848,240,404,200,'Where late-delivery exposure is highest',{'Category':[f('dim_state','state')],'Y':[f('dim_state','latitude')],'X':[f('dim_state','longitude')],'Size':[m('Late Delivery %')],'Tooltips':[m('Late Orders'),m('Delivery Eligible Orders')]},labels());tooltip(v)
    visual('Delivery','DelayHistogram','clusteredColumnChart',28,460,590,210,'Most deliveries arrive before the promised date',{'Category':[f('fact_orders','delay_bin')],'Y':[m('Delivery Eligible Orders')]},labels())
    visual('Delivery','Drivers','decompositionTreeVisual',638,460,614,210,'Explore low-review exposure by delivery, state and category',{'Analyze':[m('Low Review %')],'ExplainBy':[f('fact_orders','delivery_group'),f('dim_state','state'),f('dim_product','category')]})
    card('Scenario','Insight','Scenario Insight',28,166,1224,58,'',15)
    v=visual('Scenario','Reduction','slicer',28,244,1224,96,'What if late deliveries fell by…',{'Values':[f('Late Reduction %','Value')]},{'data':props(mode=lit('SingleValue')),'header':props(show=lit(False)),'selection':props(singleSelect=lit(True)),'general':props(filter={'filter':categorical_filter('Late Reduction %','Value',.5)})})
    for j,(meas,label) in enumerate([('Late Orders Avoided','Late orders avoided • expected'),('Low Reviews Avoided','Low reviews avoided • estimated'),('Projected Avg Rating','Projected average rating • /5')]):card('Scenario',f'ScenarioKPI{j}',meas,28+j*414,360,394,108,label)
    visual('Scenario','BeforeAfter','clusteredColumnChart',28,488,590,182,'A rating scenario, not a causal forecast',{'Category':[f('Scenario','Scenario')],'Y':[m('Scenario Rating')]},labels())
    visual('Scenario','LateBeforeAfter','clusteredBarChart',638,488,614,182,'Late-order volume before and after the intervention',{'Category':[f('Scenario','Scenario')],'Y':[m('Scenario Late Orders')]},labels())
    card('Customers','Insight','Retention Insight',28,166,1224,58,'',17)
    visual('Customers','RFM','donutChart',28,240,390,215,'Five RFM segments guide differentiated outreach',{'Category':[f('dim_customer','rfm_segment')],'Y':[m('Customers by RFM Segment')]},labels())
    visual('Customers','RevenueState','clusteredBarChart',438,240,514,215,'Customer-state revenue identifies market concentration',{'Category':[f('dim_state','state')],'Y':[m('Total Revenue')]},labels())
    card('Customers','Repeat','Repeat Customer %',972,240,280,100,'Repeat purchase rate')
    card('Customers','CustomersCount','Delivered Customers',972,355,280,100,'Delivered customers')
    visual('Customers','SegmentCounts','clusteredBarChart',28,475,490,195,'Customer count by snapshot RFM segment',{'Category':[f('dim_customer','rfm_segment')],'Y':[m('Customers by RFM Segment')]},labels())
    v=visual('Customers','TopSellers','tableEx',538,475,714,195,'Seller contribution | sorted by gross revenue',{'Values':[f('dim_seller','seller_id'),f('dim_seller','seller_state'),m('Total Revenue'),m('Orders'),m('Late Delivery %')]},{'grid':props(gridVertical=lit(False),gridHorizontal=lit(True)),'columnHeaders':props(fontColor=color(NAVY),fontSize=lit(10)),'values':props(fontSize=lit(10))})
    v['visual']['query']['sortDefinition']={'sort':[{'field':field('fact_orders','Total Revenue',True),'direction':'Descending'}]}
    page('Tooltip','Revenue & delivery context',True,480,320)
    PAGE['Tooltip']['pageBinding']={'name':'TooltipBinding','type':'Tooltip'}
    text('Tooltip','TipTitle','REVENUE & DELIVERY CONTEXT',18,12,444,32,16,NAVY)
    for j,(meas,label) in enumerate([('Total Revenue','Gross revenue'),('Revenue MoM %','Revenue MoM'),('Late Delivery %','Late deliveries'),('Low Review %','Low reviews')]):card('Tooltip',f'Tip{j}',meas,18+(j%2)*232,58+(j//2)*118,212,100,label,22)
    page('Detail','State & Category Detail',True)
    PAGE['Detail']['pageBinding']={'name':'DetailBinding','type':'Drillthrough','parameters':[{'name':'State','boundFilter':'DetailState','fieldExpr':field('dim_state','state')},{'name':'Category','boundFilter':'DetailCategory','fieldExpr':field('dim_product','category')}]}
    PAGE['Detail']['filterConfig']={'filters':[{'name':'DetailState','field':field('dim_state','state'),'type':'Categorical','howCreated':'Drillthrough'},{'name':'DetailCategory','field':field('dim_product','category'),'type':'Categorical','howCreated':'Drillthrough'}]}
    text('Detail','DetailTitle','STATE & CATEGORY DETAIL',28,25,950,48,24,NAVY)
    button('Detail','Back','Back to overview','Executive',1090,160)
    visual('Detail','DetailTable','tableEx',28,100,1224,565,'Order-level detail | category / seller metrics reflect matching orders',{'Values':[f('fact_orders','order_id'),f('dim_state','state'),f('fact_orders','order_status'),f('fact_orders','purchase_date'),m('Total Revenue'),m('Avg Review Score'),m('Late Delivery %')]})
    write(D/'pages/pages.json',{'$schema':BASE+'definition/pagesMetadata/1.0.0/schema.json','pageOrder':[n for n,_ in PAGES]+['Tooltip','Detail'],'activePageName':'Executive'})
    for n,p in PAGE.items():
        for v in VIS[n]:
            if v['visual']['visualType'] in ['clusteredBarChart','clusteredColumnChart'] and v['name'] not in ['DelayHistogram','BeforeAfter']:
                first=v['visual']['query']['queryState']['Y']['projections'][0]['field']
                v['visual']['query']['sortDefinition']={'sort':[{'field':first,'direction':'Descending'}]}
        write(D/f'pages/{n}/page.json',p)
        for v in VIS[n]:write(D/f'pages/{n}/visuals/{v["name"]}/visual.json',v)
    write(OUT/'report_inventory.json',{n:[{'name':v['name'],'type':v['visual']['visualType'],'position':v['position']} for v in vs] for n,vs in VIS.items()})
    reset={'$schema':BASE+'definition/bookmark/1.0.0/schema.json','name':'Reset','displayName':'Reset filters • 50% scenario','options':{'suppressActiveSection':True,'suppressDisplay':True,'suppressData':False},'explorationState':{'version':'1.3','activeSection':'Executive','sections':{}}}
    for n,_ in PAGES:
        vc={}
        for v in VIS[n]:
            if v['visual']['visualType']=='slicer':
                changes={'merge':{'general':props(filter={'filter':categorical_filter('Late Reduction %','Value',.5)})}} if v['name']=='Reduction' else {'remove':[{'object':'general','property':'filter','selector':{}}]}
                vc[v['name']]={'singleVisual':{'visualType':'slicer','objects':changes}}
        reset['explorationState']['sections'][n]={'visualContainers':vc}
    write(D/'bookmarks/Reset.bookmark.json',reset)
    write(D/'bookmarks/bookmarks.json',{'$schema':BASE+'definition/bookmarksMetadata/1.0.0/schema.json','items':[{'name':'Reset'}]})
    print(f'Report: {len(PAGE)} pages; {sum(map(len,VIS.values()))} visuals including shared controls')
if __name__=='__main__':build()
