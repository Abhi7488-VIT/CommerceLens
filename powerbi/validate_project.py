"""Validate PBIR against Microsoft's schemas, cache every dependency for repeatable offline checks."""
from pathlib import Path
import json, urllib.request, hashlib
import jsonschema
ROOT=Path(__file__).resolve().parent
CACHE=ROOT/'schemas/cache';CACHE.mkdir(parents=True,exist_ok=True)
STORE={}
def retrieve(url):
    url=url.split('#')[0]
    if url in STORE:return STORE[url]
    p=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    if not p.exists():
        try:
            # Microsoft's embedded schemas declare a dotted $id but are served at a hyphenated URL.
            fetch_url=url.replace('/schema.embedded.json','/schema-embedded.json')
            with urllib.request.urlopen(fetch_url,timeout=30) as r:p.write_bytes(r.read())
        except Exception as e:raise RuntimeError(f'{url}: {e}')
    data=json.loads(p.read_text(encoding='utf-8-sig'));STORE[url]=data;return data
results=[]
for p in sorted(ROOT.glob('CommerceLens.Report/**/*.json'))+list(ROOT.glob('CommerceLens.Report/*.pbir'))+list(ROOT.glob('*.pbip'))+list(ROOT.glob('CommerceLens.SemanticModel/*.pbism')):
    obj=json.loads(p.read_text(encoding='utf-8-sig'))
    if '$schema' not in obj:continue
    try:
        url=obj['$schema'];schema=retrieve(url)
        resolver=jsonschema.RefResolver(url,schema,handlers={'https':retrieve},store=STORE)
        errors=list(jsonschema.Draft7Validator(schema,resolver=resolver).iter_errors(obj))
        if errors:
            for e in errors:results.append({'file':str(p.relative_to(ROOT)),'result':'FAIL','path':list(e.path),'message':e.message})
        else:results.append({'file':str(p.relative_to(ROOT)),'result':'PASS'})
    except Exception as e:results.append({'file':str(p.relative_to(ROOT)),'result':'ERROR','message':str(e)})
(ROOT/'validation/schema_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
bad=[r for r in results if r['result']!='PASS']
print(json.dumps(bad,indent=2));print(f'{len(results)-len(bad)} passed; {len(bad)} failed or unavailable')
raise SystemExit(bool(bad))
