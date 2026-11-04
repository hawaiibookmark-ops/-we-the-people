import json,re,os,glob,sys
from lib import now,STATUS
FED=json.load(open('/workspace/wtp-repo/public/data/federal.json'))
NAMES={'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado','CT':'Connecticut','DE':'Delaware','FL':'Florida','GA':'Georgia','HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi','MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming'}
LINKS=json.load(open('official_links.json'))
OFFICE_ORDER={'US Senate':0,'Governor':1,'US House':2,'Statewide Office':2.5,'Ballot Measure':3,'Ballot Measure (statewide)':3,'State Senate':4,'State House':5,'OHA Trustee':6,'County Mayor':7,'County Council':8,'Ballot Measure (county)':9}
def toks(s): return re.findall(r"[A-Z']+",s.upper())
def incumbency(st,c):
    f=FED.get(st) or {}
    if c['office']=='US Senate': pool=f.get('senate') or []
    elif c['office']=='US House':
        d=c['district']; key='00' if d in('At-large',None) else f'{int(d):02d}'
        pool=(f.get('house') or {}).get(key) or (f.get('house') or {}).get('00') if d=='At-large' else (f.get('house') or {}).get(key) or []
    else: return
    for cd in c['candidates']:
        nt=toks(re.sub(r'\(.*?\)','',cd['name'])); val=None
        for p in pool:
            sn,_,fn=p['name'].partition(','); st_=toks(sn); ft=toks(fn)
            if st_ and all(t in nt for t in st_) and ft and (ft[0] in nt or ft[0][0]==nt[0][0]):
                ic=(p.get('incumbent_challenge') or '')
                val=True if ic=='Incumbent' else False if ic in('Challenger','Open seat') else None; break
        cd['incumbent']=val
        if val is not None: cd['incumbent_source']='FEC candidate file (incumbent/challenger/open-seat code)'
def sortkey(c):
    d=c.get('district')
    try: dn=int(re.sub(r'\D','',str(d)) or 0)
    except: dn=0
    return (OFFICE_ORDER.get(c['office'],50),c.get('jurisdiction') or '',dn,c['title'])
def build(outdir,only=None):
    idx=[]; 
    for st,nm in NAMES.items():
        raw=f'out/{st}.raw.json'
        d={'state':st,'name':nm,'election_date':'2026-11-03','links':LINKS.get(st,{})}
        if os.path.exists(raw):
            r=json.load(open(raw))
            cs=r['contests']
            for c in cs:
                incumbency(st,c)
                for cd in c['candidates']:
                    f=cd.pop('official_incumbent_flag',None)
                    if f and cd.get('incumbent') is not True:
                        cd['incumbent']=True; cd['incumbent_source']='Official results feed marks candidate (I)'
                    cd.setdefault('incumbent',None)
                    if cd.get('incumbent') is None: cd.pop('incumbent_source',None)
                # normalize
                c.setdefault('jurisdiction',nm if False else 'Statewide' if c['office'] in('US Senate','Governor','Statewide Office','Ballot Measure','Ballot Measure (statewide)') else None)
            cs.sort(key=sortkey)
            for i,c in enumerate(cs,1): c['id']=f'{st.lower()}-{i:03d}'
            d.update({'status':STATUS,'results_status':'unofficial_results','source_url':r['source_url'],'retrieved_at':r['retrieved_at'],'results_as_of':r.get('results_as_of'),'official_results_flag':r.get('official_results_flag'),'contests':cs,'notes':r.get('notes'),'official_pdfs':r.get('official_pdfs')})
            d['summary']={'contests':len(cs),'by_office':{}}
            for c in cs: d['summary']['by_office'][c['office']]=d['summary']['by_office'].get(c['office'],0)+1
            e={'state':st,'name':nm,'status':STATUS,'results_status':'unofficial_results','contests':len(cs),'by_office':d['summary']['by_office'],'source_url':r['source_url'],'retrieved_at':r['retrieved_at'],'results_as_of':r.get('results_as_of'),'file':f'{st.lower()}/index.json','notes':r.get('notes')}
        else:
            pend=json.load(open('pending.json')).get(st,{})
            d.update({'status':'Results pending from official source','results_status':'pending','source_url':LINKS.get(st,{}).get('results'),'retrieved_at':now(),'contests':[],'pending_reason':pend.get('reason','Official results page could not be read by the scraper at retrieval time.'),'summary':{'contests':0,'by_office':{}}})
            e={'state':st,'name':nm,'status':d['status'],'results_status':'pending','contests':0,'by_office':{},'source_url':d['source_url'],'retrieved_at':d['retrieved_at'],'results_as_of':None,'file':f'{st.lower()}/index.json','notes':d['pending_reason']}
        os.makedirs(f'{outdir}/{st.lower()}',exist_ok=True)
        json.dump(d,open(f'{outdir}/{st.lower()}/index.json','w'),ensure_ascii=False,indent=1)
        idx.append(e)
    top={'product':'We The People','section':'Election Results','election_date':'2026-11-03','generated_at':now(),'status_label':STATUS,
         'rules':['Official state sources only. No news outlets, AP, Ballotpedia or BallotReady.','All counts are unofficial and not yet certified; they change as counties report and states canvass.','"Leading" means highest vote count in the source at retrieval time. It is not a race call.','Vote share is each choice\'s share of votes cast for listed choices in that contest. It can differ from a source that includes blank votes in the base.','Incumbent flags come from the official FEC candidate file where available. Blank means the source did not say.'],
         'states':idx,'counts':{'states_with_results':sum(1 for e in idx if e['results_status']=='unofficial_results'),'states_pending':sum(1 for e in idx if e['results_status']=='pending')}}
    json.dump(top,open(f'{outdir}/index.json','w'),ensure_ascii=False,indent=1)
    return top
if __name__=='__main__':
    t=build(sys.argv[1] if len(sys.argv)>1 else 'build/results'); print(t['counts'])
