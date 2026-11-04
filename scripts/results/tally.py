import re,json,sys
from lib import *
A='https://enr-results-api.totalresults.com'
CFG={'AR':('arkansas','https://arkansas.tally-enr.com/')}
def run(st):
    cid,page=CFG[st]; ts=now()
    lst=get(f'{A}/Election/GetElectionList?cid={cid}').json()
    el=[e for e in lst if e['electionDate'].startswith('2026-11-03')][0]; eid=el['electionID']
    info=get(f'{A}/Election/GetElectionInfo?cId={cid}').json()
    srch=get(f'{A}/Contest/GetContestSearchList?cid={cid}&electionID={eid}').json()['response']['contests']
    parties={k:v['partyName'] for k,v in info['response']['parties'].items()}
    cs=[]; counties={}; asof=None; official=None
    locs={}
    for k,v in info['response']['locations'].items(): locs[v['locationID']]=v['locationName']
    for typ,off in [('Federal',None),('Statewide',None),('State Senate','State Senate'),('State Representative','State House')]:
        d=get(f'{A}/Contest/GetContestResults?cId={cid}&electionID={eid}&contestType={typ.replace(" ","%20")}').json()
        asof=d['lastUpdated']; official=d['isOfficial']
        for cidk,r in d['response']['contests'].items():
            s=srch[cidk]; name=s['contestName'].strip(); ch=s['choices']
            cands=[]
            for c in r['choices']:
                m=ch.get(c['choiceID'],{}); nm=m.get('name','')
                mm=re.match(r'^([A-Z]{2,4})\s+(.*)$',nm)
                party=parties.get(c.get('partyID')) if c.get('partyID') else None
                if mm and typ!='Statewide' or (mm and not re.search('ISSUE',nm)): nm=mm.group(2)
                nm=re.sub(r'^(State Senator|State Senate|State Representative|State Rep\.?|Senator|Representative|Rep\.?)\s+','',nm)
                cands.append({'name':nm,'party':party,'votes':c['totalVotes'],'write_in':bool(m.get('isWriteIn'))})
            for c in r.get('writeInChoices') or []:
                if c.get('totalVotes'): cands.append({'name':'Write-in','party':None,'votes':c['totalVotes'],'write_in':True})
            rep={'unit':'precincts','reporting':r['precinctsReporting'],'total':r['totalPrecincts']}
            if re.match(r'U\.S\. Senate',name): o,dist,t=('US Senate',None,'U.S. Senate')
            elif re.match(r'U\.S\. Congress',name): n=int(re.search(r'(\d+)',name).group(1)); o,dist,t=('US House',str(n),f'U.S. Representative, District {n}')
            elif name=='Governor': o,dist,t=('Governor',None,'Governor')
            elif re.match(r'ISSUE NO',name):
                cands=[{**c,'name':'For' if c['name'].startswith('FOR') else 'Against' if c['name'].startswith('AGAINST') else c['name']} for c in cands]
                o,dist,t=('Ballot Measure',name.title(),name.title().replace('No.','No.'))
            elif typ=='Statewide': o,dist,t=('Statewide Office',None,name)
            elif off: n=int(re.search(r'(\d+)',name).group(1)); o,dist,t=(off,str(n),f"State {'Senate' if off=='State Senate' else 'Representative'} District {n}")
            else: continue
            c=contest(o,dist,t,cands,page,ts,rep,asof,s.get('voteFor') or 1)
            if o in('US Senate','Governor','Statewide Office','Ballot Measure'): c['jurisdiction']='Statewide'
            if r.get('hasRecount'): c['notes']=(c.get('notes','')+' Source marks this contest as having a recount.').strip()
            cs.append(c)
            counties[cidk]={'title':t,'office':o,'district':dist,'locations':{locs.get(l,l):{'precincts':[v['precinctsReporting'],v['totalPrecincts']],'votes':{ch.get(x['choiceID'],{}).get('name'):x['totalVotes'] for x in v['choices']}} for l,v in (r.get('locations') or {}).items()}}
    json.dump(counties,open(f'out/{st}.counties.json','w'),ensure_ascii=False)
    return {'state':st,'election_date':'2026-11-03','source_url':page,'retrieved_at':ts,'results_as_of':asof,'official_results_flag':official,'contests':cs}
if __name__=='__main__':
    for st in sys.argv[1:]:
        r=run(st); json.dump(r,open(f'out/{st}.raw.json','w'),ensure_ascii=False,indent=1)
        for c in r['contests'][:30]: print(c['office'],c['district'],c['title'],c['total_votes'],c.get('leading'),c['reporting'],[x['name'] for x in c['candidates']][:3])
