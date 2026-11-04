import json,re
from lib import *
B='https://ctemspublic.tgstg.net/ng-app/data/election/108'
def run():
    ts=now(); ver=get(B+'/Version.json').json()['Version']
    f=lambda n: get(f'{B}/{ver}/{n}.json').json()
    L=f('Lookupdata'); V=f('stateVotes_Electiondata'); E=f('election_Electiondata')
    offs={}
    for o in L['officeList']:
        for k,v in o.items(): offs[k]=v
    m=re.match(r'(\d+) of (\d+)',E['PR'])
    rep={'unit':'precincts','reporting':int(m.group(1)),'total':int(m.group(2))}
    cs=[]
    for oid,rows in V.items():
        o=offs.get(oid)
        if not o: continue
        title=o['NM']; k=classify(title)
        if not k: continue
        cands=[]
        for r in rows:
            for cid,val in r.items():
                c=L['candidateIds'].get(cid,{}); p=L['partyIds'].get(c.get('P'),{})
                cands.append({'name':c.get('NM','?'),'party':p.get('NM'),'votes':int(val['V'].replace(',','')),'write_in':False})
        merged={}
        for c in cands:
            m=merged.setdefault(c['name'],{'name':c['name'],'party':[],'votes':0,'write_in':False,'lines':[]})
            m['votes']+=c['votes']; m['party'].append(c['party']); m['lines'].append({'party':c['party'],'votes':c['votes']})
        cands=[dict({k:v for k,v in m.items() if k!='lines'},party=' / '.join(p for p in m['party'] if p),party_lines=m['lines']) for m in merged.values()]
        cs.append(contest(k[0],k[1],title,cands,'https://ctemspublic.tgstg.net/',ts,rep,None,1))
    return {'state':'CT','election_date':'2026-11-03','source_url':'https://ctemspublic.tgstg.net/','retrieved_at':ts,'results_as_of':None,'contests':cs,'notes':'Connecticut State Election Night Reporting: '+E['PR']+' precincts; '+E['T']+' towns reporting. A candidate listed on more than one party line is shown once with votes summed across lines (per-line votes kept in party_lines).'}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/CT.raw.json','w'),ensure_ascii=False,indent=1)
    for c in r['contests']: print(c['office'],c['district'],c['title'],c['total_votes'],c['leading'],[(x['name'],x['party'],x['votes']) for x in c['candidates'][:3]])
