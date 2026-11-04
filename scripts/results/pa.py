import json,re,sys
from lib import *
B='https://www.electionreturns.pa.gov/api/ElectionReturn/'
EID='electionid=117&electiontype=G&isactive=1'
def j(u):
    r=get(u); t=r.json()
    return json.loads(t) if isinstance(t,str) else t
def cand(x,tick=False):
    n=x['CandidateName'].strip(); rm=(x.get('RunningMateName') or '').strip()
    if rm and tick:
        if ',' in rm: l,_,f=rm.partition(','); rm=f.strip()+' '+l.strip()
        n=f'{n} / {rm}'
    return {'name':n,'party':x['PartyName'],'votes':int(x['Votes']),'write_in':False}
def run():
    ts=now(); cs=[]
    dm=j(B+'GetOfficeNames?countyName=&methodName=GetOfficeNames&'+EID)
    msg=json.loads(dm['Table1'][0]['DashboardMessage'])
    rep={'unit':'voting districts (in-person ballots reporting)','reporting':int(msg['ReportingDistrict']),'total':int(msg['VotingDistrict'])}
    try: asof=j(B+'GetUpdatedTimeStamp?methodName=GetUpdatedTimeStamp&'+EID)
    except Exception: asof=None
    asof=str(asof) if asof else None
    src='https://www.electionreturns.pa.gov/'
    g=j(B+'GET?methodName=GetSummaryData&'+EID)['Election']['Governor'][0]['Statewide']
    cs.append(contest('Governor',None,'Governor and Lieutenant Governor',[cand(x,True) for x in g],src,ts,rep,asof,1))
    h=j(B+'GetOfficeData?officeId=11&methodName=GetOfficeDetails&'+EID)['Election']['Representative in Congress'][0]
    for key,v in h.items():
        d=v[0]; num=re.match(r'(\d+)',d['District']).group(1)
        cs.append(contest('US House',str(int(num)),f"Representative in Congress, {d['District']}",[cand(x) for x in d['Candidates']],src,ts,rep,asof,1))
    return {'state':'PA','election_date':'2026-11-03','source_url':src,'retrieved_at':ts,'results_as_of':None,'contests':cs,'notes':'Source banner: '+msg.get('DistrictMessage','').strip()}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/PA.raw.json','w'),ensure_ascii=False,indent=1)
    print(r['notes']); 
    for c in r['contests']: print(c['office'],c['district'],c['total_votes'],c['leading'],c['margin_pct'])
