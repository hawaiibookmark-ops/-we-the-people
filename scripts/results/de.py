import re,json
from collections import OrderedDict
from lib import *
SRC='https://elections.delaware.gov/results/enr/GE2026.html'
API='https://elections.delaware.gov/results/enr/Election_StatewideResults_ID_GE2026.json'
def iv(x): return int(re.sub(r'\D','',str(x)) or 0)
def run():
    ts=now(); rows=get(API).json(); g=OrderedDict()
    for r in rows: g.setdefault(r['Contest Title'],[]).append(r)
    cs=[]; asof=None
    for t,rs in g.items():
        title=re.sub(r'\s+',' ',t).strip(); r0=rs[0]; asof=r0.get('ReportTime') or asof
        cands=[{'name':r['Candidate Name'],'party':(r['Party Name'] or '').replace(' Party','') or None,'votes':iv(r['Total Votes']),'write_in':bool(re.search('write',r['Candidate Name'],re.I))} for r in rs]
        rep={'unit':'precincts','reporting':r0['Total Precincts'] and r0['Precincts Reported'],'total':r0['Total Precincts']}
        md=re.search(r'(?:state senator|state representative)\s+district\s+(\d+)',title,re.I)
        if re.match(r'u\.?s\.? senator|u\.s\. senator',title,re.I): off,d=('US Senate',None)
        elif re.match(r'representative in congress',title,re.I): off,d=('US House','At-large')
        elif re.match(r'governor',title,re.I): off,d=('Governor',None)
        elif md and re.match('state senator',title,re.I): off,d=('State Senate',str(int(md.group(1))))
        elif md: off,d=('State House',str(int(md.group(1))))
        elif re.match(r'attorney general|auditor|state treasurer|insurance|lieutenant|secretary',title,re.I): off,d=('Statewide Office',None)
        elif is_measure_title(title): off,d=('Ballot Measure',title)
        else: print('skip',title); continue
        if off=='US Senate' or off=='Governor': title=title
        c=contest(off,d,title,cands,SRC,ts,rep,asof,1)
        if off in('US Senate','Governor','Statewide Office','Ballot Measure'): c['jurisdiction']='Statewide'
        cs.append(c)
    return {'state':'DE','election_date':'2026-11-03','source_url':SRC,'api_url':API,'retrieved_at':ts,'results_as_of':asof,'contests':cs}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/DE.raw.json','w'),ensure_ascii=False,indent=1)
    for c in r['contests']: print(c['office'],c['district'],c['title'],c['total_votes'],c.get('leading'),c['reporting'])
