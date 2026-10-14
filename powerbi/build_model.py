from pathlib import Path
import json, uuid
from model_queries import SCHEMA, partition
from model_measures import M
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'powerbi'
MODEL=OUT/'CommerceLens.SemanticModel'
# Power BI Desktop rejects a table named 'Measures'; measures are homed on the order fact.
MEASURE_HOME='fact_orders'
DATA_FOLDER=r'C:\CommerceLens\powerbi\data'
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False) if isinstance(obj,(dict,list)) else obj,encoding='utf-8')
def build():
    tables=[]
    for name,cols in SCHEMA.items():
        columns=[]
        for col,typ in cols:
            c=dict(name=col,dataType=typ,sourceColumn=col,summarizeBy='none')
            if col.endswith('_id') or (name.startswith('fact') and col not in ['order_status','review_score','delivery_group','delay_bin']):c['isHidden']=True
            if typ=='dateTime': c.update(formatString='dd MMM yyyy',annotations=[dict(name='UnderlyingDateTimeDataType',value='Date')])
            if col=='Date':c['isKey']=True
            if name=='dim_date' and col=='month_name':c['sortByColumn']='month'
            if name=='dim_state' and col=='state':c['dataCategory']='StateOrProvince'
            if col in ['latitude','longitude','country']:c['dataCategory']={'latitude':'Latitude','longitude':'Longitude','country':'Country'}[col]
            columns.append(c)
        t=dict(name=name,columns=columns,partitions=[dict(name=name,mode='import',source=dict(type='m',expression=partition(name)))])
        if name=='dim_date':t['dataCategory']='Time'
        if name=='cleaning_log':t['isHidden']=True
        if name==MEASURE_HOME:t=dict(name=t['name'],columns=t['columns'],measures=M,partitions=t['partitions'])
        tables.append(t)
    tables.append(dict(name='Late Reduction %',columns=[dict(name='Value',dataType='double',sourceColumn='Value',formatString='0%',summarizeBy='none',extendedProperties=[dict(type='json',name='ParameterMetadata',value={'version':0})])],partitions=[dict(name='Late Reduction %',mode='import',source=dict(type='m',expression='Table.FromColumns({List.Transform({0..20}, each _ / 20)}, type table [Value=number])'))]))
    tables.append(dict(name='Scenario',columns=[dict(name='Scenario',dataType='string',sourceColumn='Scenario'),dict(name='Sort',dataType='int64',sourceColumn='Sort',isHidden=True)],partitions=[dict(name='Scenario',mode='import',source=dict(type='m',expression='#table(type table [Scenario=text, Sort=Int64.Type], {{"Before",1},{"After",2}})'))]))
    tables[-1]['columns'][0]['sortByColumn']='Sort'
    rels=[]
    for ft,fc,dt,dc in [('fact_orders','customer_unique_id','dim_customer','customer_unique_id'),('fact_orders','purchase_date','dim_date','Date'),('fact_orders','state','dim_state','state'),('fact_order_items','order_id','fact_orders','order_id'),('fact_order_items','product_id','dim_product','product_id'),('fact_order_items','seller_id','dim_seller','seller_id')]:
        rels.append(dict(name=str(uuid.uuid5(uuid.NAMESPACE_DNS,ft+fc+dt)),fromTable=ft,fromColumn=fc,toTable=dt,toColumn=dc,fromCardinality='many',toCardinality='one',crossFilteringBehavior='oneDirection',isActive=True))
    expressions=[dict(name='DataFolder',kind='m',expression=f'"{DATA_FOLDER}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',annotations=[dict(name='PBI_ResultType',value='Text')])]
    model=dict(name='CommerceLens',compatibilityLevel=1600,model=dict(culture='en-US',defaultPowerBIDataSourceVersion='powerBI_V3',sourceQueryCulture='en-US',expressions=expressions,tables=tables,relationships=rels,annotations=[dict(name='__PBI_TimeIntelligenceEnabled',value='0')]))
    write(MODEL/'model.bim',model)
    write(MODEL/'definition.pbism',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json','version':'1.0','settings':{}})
    write(OUT/'CommerceLens.pbip',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json','version':'1.0','artifacts':[{'report':{'path':'CommerceLens.Report'}}],'settings':{'enableAutoRecovery':True}})
    text='// CommerceLens Power Query. Each table reads one CSV written by export_star_schema.py; no merges or query references.\nsection CommerceLens;\n\nshared DataFolder = '+expressions[0]['expression']+';\n\n'
    for t in tables:text+='// '+t['name']+'; enable load for this query.\nshared #"'+t['name']+'" = '+t['partitions'][0]['source']['expression']+';\n\n'
    write(OUT/'power_query.m',text)
    text=('// CommerceLens measures, home table: '+MEASURE_HOME+'. Formats and display folders are applied in model.bim.\n'
          '// DAX query view: paste this whole file, then use "Update model with changes" to add every measure.\n'
          '// Format strings are not part of DEFINE MEASURE; the intended format is in each comment.\nDEFINE\n')
    for m in M:
        body='\n'.join('        '+l for l in m['expression'].split('\n'))
        text+='\n    // '+m['displayFolder']+' | '+m['description']+'\n    // Format: '+m['formatString']+'\n    MEASURE \''+MEASURE_HOME+'\'['+m['name']+'] =\n'+body+'\n'
    text+='\nEVALUATE\n    ROW("Orders", [Orders], "Total Revenue", [Total Revenue], "Late Delivery %", [Late Delivery %], "Avg Review Score", [Avg Review Score])\n'
    write(OUT/'measures.dax',text)
    print(f'Model: {len(tables)} tables, {len(rels)} one-direction relationships, {len(M)} measures')
if __name__=='__main__':build()
