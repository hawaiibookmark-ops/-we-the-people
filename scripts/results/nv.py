import json,re,collections
from lib import *
B='https://silverstateelection.nv.gov'
def flip(l):
    if ',' in l and not re.match(r'^(Yes|No|For|Against)\b',l):
        a,_,b=l.partition(','); return f'{b.strip()} {a.strip()}'.strip()
    return l
def run():
    ts=now()
    man=get(B+'/data/v2/elections/2a6d1aef-f8eb-424f-9130-ac9bdc2cced5/manifest.json').json()
    eid=man['electionId']; base=f'{B}/data/v2/elections/{eid}/'
    ov=get(base+man['overview']['path']).json()
    paths={c['contestId']:c['results']['path'] for c in man['contests']}
    parties={p['id']:p['abbreviation'] for p in ov['parties']}
    cs=[]
    for c in ov['contests']:
        title=c['name']; scope=c['scope']
        k=classify(title)
        if not k and c['kind']!='Office' and (scope.get('level') in('State','Statewide')): k=('Ballot Measure',title)
        if not k: continue
        res=get(base+paths[c['id']]).json()
        tot=collections.Counter()
        for co in res['counties']:
            for ch in co['choices']: tot[ch['choiceId']]+=(ch['votes'] or 0)
        cands=[]
        for ch in c['choices']:
            cd=ch.get('candidate') or {}
            cands.append({'name':flip(ch['label']),'party':parties.get(cd.get('partyId')) if cd else None,'votes':tot.get(ch['id'],0),'official_incumbent_flag':True if cd.get('incumbent') else None,'write_in':False})
        ct=contest(k[0],k[1],title,cands,B+'/',ts,None,man['generatedAtUtc'],c.get('voteFor') or 1)
        if res.get('officialQuestionText') or c.get('question'): ct['description']=res.get('officialQuestionText') or c.get('question')
        cs.append(ct)
    return {'state':'NV','election_date':'2026-11-03','source_url':B+'/','retrieved_at':ts,'results_as_of':man['generatedAtUtc'],'official_results_flag':ov['election']['resultsStatus']!='Unofficial','contests':cs,'_titles':[c['name'] for c in ov['contests'] if not classify(c['name'])][:20]}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/NV.raw.json','w'),ensure_ascii=False,indent=1)
    for c in r['contests']: print(c['office'],c['district'],c['title'],c['total_votes'],c['leading'])
    print(r['_titles'])
