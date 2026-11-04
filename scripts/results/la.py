import re,json
from lib import *
D='https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob='
PAGE='https://voterportal.sos.la.gov/static/20261103/RacesCandidates_Multiparish.htm'
def run():
    ts=now()
    R=get(D+'20261103/RacesCandidates_Multiparish.htm').json()['Races']
    V=get(D+'20261103/Votes_Multiparish.htm').json()['Races']['Race']
    votes={x['ID']:x for x in V}; cs=[]
    for r in R['Race']:
        lvl=r['OfficeLevel']; title=re.sub(r'\s+',' ',r['SpecificTitle']).strip(); v=votes.get(r['ID'])
        if not v: continue
        vm={c['ID']:int(c['VoteTotal']) for c in v['Choice']}
        if lvl=='140': off,dist='US Senate',None
        elif lvl=='145':
            off='US House'; dist=str(int(re.search(r'(\d+)(?:st|nd|rd|th) Congressional',title).group(1)))
        elif lvl=='998': off,dist='Ballot Measure',re.search(r'CA No\.\s*(\d+)',title).group(1)
        else: continue
        cands=[]
        for c in r['Choice']:
            d=c['Desc']; m=re.search(r'\(([A-Z]+)\)\s*$',d); party=m.group(1) if m else None
            name=re.sub(r'\s*\([A-Z]+\)\s*$','',d).replace('"',"'" if False else '"')
            cands.append({'name':clean_name(name) if off!='Ballot Measure' else name,'party':party if off!='Ballot Measure' else None,'votes':vm.get(c['ID'],0)})
        rep={'unit':'precincts','reporting':int(v['PrecinctsReporting']),'total':int(v['PrecinctsExpected'])}
        t=title if off!='Ballot Measure' else f"Constitutional Amendment {dist}: "+title.split('--',1)[1].strip()
        if off=='US House': t=f'U.S. Representative, District {dist}'
        c=contest(off,('Amendment %s'%dist) if off=='Ballot Measure' else dist,t,cands,PAGE,ts,rep,R['WriteTime']+' (Central Time, per source)',int(r.get('NumberToBeElected') or 1))
        if off=='Ballot Measure':
            c['description']=r['FullText']; c['jurisdiction']='Statewide'
        elif off=='US House' and r.get('CanHaveRunoff')=='1':
            c['notes']='Louisiana Secretary of State data marks this contest as able to have a runoff (CanHaveRunoff=1). No runoff has been stated for this contest in the feed.'
        cs.append(c)
    return {'state':'LA','election_date':'2026-11-03','source_url':'https://voterportal.sos.la.gov/graphical','retrieved_at':ts,'results_as_of':R['WriteTime']+' (Central Time, per source)','contests':cs}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/LA.raw.json','w'),ensure_ascii=False,indent=1)
    for c in r['contests']: print(c['office'],c['district'],c['title'][:70],c['total_votes'],c.get('leading'),c.get('margin_votes'),c['reporting'])
