import sys,json,re
from lib import *
CFG_AZ=('https://app.enhancedvoting.com','Arizona','110326GeneralElection')
STATEWIDE_RE=re.compile(r'^(secretary of state|attorney general|state treasurer|treasurer|superintendent|state superintendent|state school|state mine|corporation commission|lieutenant governor|auditor|state auditor|comptroller|controller|commissioner of|insurance commissioner|labor commissioner|public service commission|public utilities|railroad|land commissioner|agriculture)',re.I)
CFG={'GA':('https://results.sos.ga.gov','Georgia','11032026GeneralAndSpecialElection'),
     'UT':('https://electionresults.utah.gov','utah','General11032026'),
     'WA':('https://results.votewa.gov','washington','20261103'),
     'AZ':CFG_AZ,
     'RI':('https://electionresults.ri.gov','rhodeisland','2026StatewideGeneralElection'),
     'ID':('https://results.voteidaho.gov','id','nov2026'),
     'VA':('https://enr.elections.virginia.gov','virginia','2026-November-General')}
def run(st):
    host,j,eid=CFG[st]
    ts=now()
    api=f'{host}/results/public/api/elections/{j}/{eid}/data'
    d=get(api).json()
    page=f'{host}/results/public/{j}/elections/{eid}'
    el=d['election']
    cs=[]
    maxunits=max(((b.get('reportingStatus') or {}).get('totalUnits') or 0) for b in d['ballotItems'])
    for b in d['ballotItems']:
        title=b['name'][0]['text']
        if b.get('contestType')=='BallotMeasure' and not re.search(r'retain|retention|retained',title,re.I) and ((b.get('reportingStatus') or {}).get('totalUnits') or 0)>=0.9*maxunits:
            opts=[{'name':o['name'][0]['text'],'party':None,'votes':o['voteCount']} for o in b['summaryResults']['ballotOptions']]
            rs=b.get('reportingStatus') or {}
            rep={'unit':'counties/jurisdictions','reporting':rs.get('reportingUnits'),'total':rs.get('totalUnits')}
            c2=contest('Ballot Measure',title,title,opts,page,ts,rep,el.get('asOf'),1); c2['jurisdiction']='Statewide'
            ref=b.get('referendum') or []
            if ref:
                try: c2['description']=' '.join(x['text'] for x in ref if x.get('languageId')=='en')[:2000]
                except Exception: pass
            cs.append(c2); continue
        c=classify(title)
        m2=re.match(r'Member, House of Representatives \((\d+)(?:st|nd|rd|th) District\)',title)
        if m2: c=('US House',str(int(m2.group(1))))
        elif re.match(r'Member, United States Senate',title): c=('US Senate',None)
        if not c and b.get('contestType')=='Candidate':
            md=re.search(r'district\D{0,12}(\d+)',title,re.I) or re.search(r'\b(\d+)(?:st|nd|rd|th)? district',title,re.I)
            if re.search(r'state senat|^senate',title,re.I) and md and not re.search(r'\bu\.?s\.?\b|united',title,re.I): c=('State Senate',str(int(md.group(1))))
            elif re.search(r'state rep|state house|house of delegates|^house',title,re.I) and md and not re.search(r'\bu\.?s\.?\b|united',title,re.I): c=('State House',str(int(md.group(1))))
            elif STATEWIDE_RE.match(title.strip()) and not re.search(r'county|district',title,re.I): c=('Statewide Office',None)
        if not c: continue
        if b.get('contestType')!='Candidate': continue
        cands=[]
        for o in b['summaryResults']['ballotOptions']:
            raw=o['name'][0]['text']
            p=(o.get('party') or {}).get('abbreviation')
            cands.append({'name':clean_name(raw),'party':p,'votes':o['voteCount'],'official_incumbent_flag':bool(re.search(r'\((I|Inc)\)',raw)) or None,'write_in':bool(o.get('isWriteIn'))})
        rs=b.get('reportingStatus') or {}
        rep={'unit':'counties/jurisdictions','reporting':rs.get('reportingUnits'),'total':rs.get('totalUnits')}
        vf=(b.get('voteFor') or [{}])[0].get('text','')
        m=re.search(r'(\d+)',vf)
        cs.append(contest(c[0],c[1],title,cands,page,ts,rep,el.get('asOf'),int(m.group(1)) if m else 1))
        if c[0] in('Statewide Office',): cs[-1]['jurisdiction']='Statewide'
    return {'state':st,'election_date':'2026-11-03','source_url':page,'api_url':api,'retrieved_at':ts,
            'results_as_of':el.get('asOf'),'official_results_flag':el.get('isOfficialResults'),'contests':cs}
if __name__=='__main__':
    for st in sys.argv[1:]:
        r=run(st); json.dump(r,open(f'out/{st}.raw.json','w'),ensure_ascii=False,indent=1)
        print(st,len(r['contests']),r['results_as_of'],r['official_results_flag'])
        for c in r['contests'][:50]: print('  ',c['office'],c['district'],c['title'],'|',c['total_votes'],c.get('leading'),c['reporting'])
