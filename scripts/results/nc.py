import csv,collections,json,zipfile,io,re
from lib import *
URL='https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2026_11_03/results_pct_20261103.zip'
PAGE='https://er.ncsbe.gov/?election_dt=11/03/2026&county_id=0&office=FED&contest=0'
def run():
    r=get(URL); ts=now(); lm=r.headers.get('Last-Modified')
    z=zipfile.ZipFile(io.BytesIO(r.content)); name=z.namelist()[0]
    rows=list(csv.DictReader(io.TextIOWrapper(z.open(name),encoding='utf-8',errors='replace'),delimiter='\t'))
    agg=collections.OrderedDict(); prec=collections.defaultdict(set); counties=collections.defaultdict(set)
    for x in rows:
        n=x['Contest Name']
        if not (n.startswith('US ') or n.startswith('CONSTITUTIONAL AMENDMENT') or n.startswith('GOVERNOR')): continue
        k=n; agg.setdefault(k,collections.OrderedDict())
        key=(x['Choice'].strip(),x['Choice Party'].strip())
        agg[k][key]=agg[k].get(key,0)+int(x['Total Votes'])
        prec[k].add((x['County'],x['Precinct'])); counties[k].add(x['County'])
    cs=[]
    for n,ch in agg.items():
        cands=[{'name':c,'party':p or None,'votes':v,'write_in':c.lower().startswith('write')} for (c,p),v in ch.items()]
        if n=='US SENATE': o,d=('US Senate',None); t='US Senate'
        elif n.startswith('US HOUSE'): o,d=('US House',str(int(n.split()[-1]))); t=f'US House District {int(n.split()[-1])}'
        elif n.startswith('CONSTITUTIONAL'): o,d=('Ballot Measure',n.title()); t=n.title().replace('Id','ID')
        else: continue
        c=contest(o,d,t,cands,URL,ts,{'unit':'precincts with results in file','reporting':len(prec[n]),'total':None},lm,1)
        c['notes']='Precinct-level unofficial file from NCSBE; the file does not state a total precinct count, so reporting percent is not computed.'
        cs.append(c)
    return {'state':'NC','election_date':'2026-11-03','source_url':PAGE,'data_url':URL,'retrieved_at':ts,'results_as_of':lm,'contests':cs}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/NC.raw.json','w'),ensure_ascii=False,indent=1)
    for c in r['contests']: print(c['office'],c['district'],c['title'],c['total_votes'],c.get('leading'),[ (x['name'],x['votes']) for x in c['candidates'][:3]])
