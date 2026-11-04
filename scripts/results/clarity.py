import sys,json,time,re
from lib import *
CFG={'CO':('results.enr.clarityelections.com','CO','127407','https://results.enr.clarityelections.com/CO/127407/web.345435/'),
     'IA':('electionresults.iowa.gov','IA','127077','https://electionresults.iowa.gov/IA/127077/')}
def fetch(u,tries=8):
    for i in range(tries):
        r=get(u)
        if r.status_code==200 and not r.text.lstrip().startswith('<!DOC'): return r
        time.sleep(3+i*2)
    raise RuntimeError('fail '+u)
def run(st):
    h,s,eid,_=CFG[st]
    base=f'https://{h}/{s}/{eid}'
    ver=fetch(base+'/current_ver.txt').text.strip()
    ts=now()
    summ=json.loads(fetch(f'{base}/{ver}/json/en/summary.json').text)
    sett=json.loads(fetch(f'{base}/{ver}/json/en/electionsettings.json').text)['settings']
    page=f'https://{h}/{s}/{eid}/{ver}/'
    cs=[]
    for c in summ:
        t=c['C']
        k=classify(t,c['CAT'])
        if not k and re.search(r'^state\b',c['CAT'],re.I) and is_measure_title(t) and not re.search(r'city|town|county|school|district|public measure',t,re.I):
            k=('Ballot Measure',t)
        if not k:
            continue
        cands=[{'name':n.title() if n.isupper() else n,'party':p,'votes':int(v),'write_in':bool(re.search(r'write',n,re.I))} for n,p,v in zip(c['CH'],c['P'],c['V'])]
        rep={'unit':'precincts','reporting':c.get('PR'),'total':c.get('TP')}
        cs.append(contest(k[0],k[1],t,cands,f'https://{h}/{s}/{eid}/{ver}/json/en/summary.json',ts,rep,None,c.get('VF') or 1))
    return {'state':st,'election_date':'2026-11-03','source_url':f'https://{h}/{s}/{eid}/','retrieved_at':ts,'results_as_of':None,'raw_version':ver,'contests':cs,'_all_titles':[(c['CAT'],c['C']) for c in summ]}
if __name__=='__main__':
    for st in sys.argv[1:]:
        r=run(st); json.dump(r,open(f'out/{st}.raw.json','w'),ensure_ascii=False,indent=1)
        print(st,len(r['contests']),r['raw_version'])
        for c in r['contests']: print('  ',c['office'],c['district'],c['title'],'|',c['total_votes'],c.get('leading'),c['reporting'])
        print([t for t in r['_all_titles'] if not classify(t[1])][:60])
