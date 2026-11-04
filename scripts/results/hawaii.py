import csv,io,re,json,subprocess
from lib import *
SRC='https://elections.hawaii.gov/wp-content/results/2026%20General/summary.txt'
RES='https://elections.hawaii.gov/election-results/'
PDFS={'State of Hawaii':'histatewide','County of Hawaii':'coh','County of Maui':'com','County of Kauai':'cok','City and County of Honolulu':'cch'}
PARTY={'D':'Democratic','R':'Republican','L':'Libertarian','G':'Green','N':'Nonpartisan'}
ROMAN={'I':1,'II':2,'III':3,'IV':4,'V':5,'VI':6,'VII':7,'VIII':8,'IX':9}
def disp(n):
    if ',' not in n: return n.strip()
    last,first=[x.strip() for x in n.split(',',1)]
    first=re.sub(r'\s*\([^)]*\.[^)]*\)','',first).strip()
    if last.isupper(): last=' '.join(('Mc'+w[2:].title() if w.startswith('MC') and len(w)>2 else w.title()) for w in last.split())
    jr=''
    m=re.match(r'^(.*?)(?:,)?\s*(Jr\.?|Sr\.?|II|III|IV)$',first)
    if m: first=m.group(1).strip().rstrip(','); jr=' '+m.group(2)
    return f'{first} {last}{jr}'.strip()
def run():
    ts=now()
    rr=get(SRC); txt=rr.content.decode('utf-8','replace'); lm=rr.headers.get('Last-Modified')
    open('raw/hi_summary.txt','w').write(txt)
    pdf={}
    for k,f in PDFS.items():
        pdf[k]=open(f'raw/hi_{f}.txt').read() if f!='x' else ''
    rows=list(csv.reader(io.StringIO(txt),delimiter='\t',quotechar='"'))
    by={}
    for r in rows[2:]:
        if len(r)<21: continue
        by.setdefault(r[0],[]).append(r)
    contests=[]
    for cid,rs in by.items():
        r0=rs[0]; title=r0[1].strip(); ctype=r0[3]
        cands=[]
        for r in rs:
            raw=r[15]
            m=re.match(r'^\(([A-Z])\)\s*(.*)$',raw,re.S)
            party=PARTY.get(m.group(1),m.group(1)) if m else None
            body=m.group(2) if m else raw
            lines=[l.strip() for l in body.split('\n') if l.strip()]
            if len(lines)>=4 and lines[1].upper().startswith('FOR GOVERNOR'):
                official=f'{lines[0]} / {lines[2]}'; name=f'{disp(lines[0])} / {disp(lines[2])}'
            else:
                official=' '.join(lines); name=disp(official) if ctype=='OF' else official.title() if False else disp(official)
            cands.append({'name':name,'official_name':official,'party':party,'votes':int(r[20]),'mail_votes':int(r[18]),'in_person_votes':int(r[19])})
        rep={'unit':'precincts','reporting':int(r0[13]),'total':int(r0[12])}
        blank=int(r0[5])+int(r0[6]); over=int(r0[7])+int(r0[8])
        surn=[c['official_name'].split(',')[0].replace('(','').strip() for c in cands]
        # jurisdiction
        hits=[k for k in pdf if k!='State of Hawaii' and all(s and s in pdf[k] for s in surn)]
        st_hit=all(s in pdf['State of Hawaii'] for s in surn)
        office=None; dist=None; jur='State of Hawaii'; disp_title=title; ttl=title
        if re.match(r'U\.S\. Representative',title):
            office='US House'; dist=str(ROMAN[title.split('Dist')[1].strip()])
        elif title.startswith('Governor'): office='Governor'
        elif title.startswith('State Senator'): office='State Senate'; dist=re.search(r'Dist (\d+)',title).group(1)
        elif title.startswith('State Representative'): office='State House'; dist=re.search(r'Dist (\d+)',title).group(1)
        elif 'Trustee' in title: office='OHA Trustee'; ttl=title
        elif title=='Mayor' or title.startswith('Councilmember'):
            office='County Mayor' if title=='Mayor' else 'County Council'
            if len(hits)==1: jur=hits[0]
            elif len(hits)>1:
                jur='|'.join(hits)
            ttl=title
        elif ctype=='MS':
            if title.startswith('Question #'):
                office='Ballot Measure (statewide)'
                n=title.split('#')[1]
                ttl={'1':'Constitutional Amendment — Question #1: Increasing the Timeframe for the Hawaii Senate to Consider and Act on Judicial Appointments','2':'Constitutional Amendment — Question #2: Directing the Legislature to Establish Procedures for Counties to Issue RISE Bonds, Exempt from County Debt Limits'}[n]
            else:
                office='Ballot Measure (county)'
                if title.startswith('Charter Question #'):
                    n=title.split('#')[1]; jur='City and County of Honolulu'
                    m=re.search(r'Honolulu %s: ([^\n]*?)(?:\s{2,}|$)'%n,pdf['City and County of Honolulu'])
                    ttl=f'Honolulu Charter Question #{n}'+(f': {m.group(1).strip()}' if m else '')
                elif title.startswith('Maui:'): jur='County of Maui'; ttl=title
                elif title.startswith('1. Hawai'): jur='County of Hawaii'; ttl="Hawaii County Charter Question 1: County Auditor's Power to Employ"
                else: jur='County of Kauai'; ttl='Kauai Charter Question 1: Planning Commission Appeals Process'
        else:
            office='Other'
        if office in('Mayor','County Mayor','County Council') and jur=='State of Hawaii': jur='UNRESOLVED'
        c=contest(office,dist,ttl,cands,SRC,ts,rep,None,1)
        c['jurisdiction']=jur
        c['official_contest_id']=cid; c['official_contest_title']=title
        c['blank_votes']=blank; c['over_votes']=over
        c['registered_voters']=int(r0[11])
        m=re.search(r'Number To Vote For: (\d+)',pdf.get('State of Hawaii','')+''.join(pdf.values())) 
        if 'At-Large Trustee' in title: c['vote_for']=3
        c['pct_basis']='share of votes cast for listed choices (blank and over votes excluded)'
        contests.append(c)
    return {'state':'HI','election_date':'2026-11-03','source_url':RES,'data_url':SRC,'retrieved_at':ts,'results_as_of':lm,'printed_by_source':'Printed on 11/03/2026 09:02:44 pm HST (statewide PDF); summary.txt fetched live','contests':contests,'official_pdfs':{k:f'https://elections.hawaii.gov/wp-content/results/2026%20General/{v}.pdf' for k,v in PDFS.items()}}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/HI.raw.json','w'),ensure_ascii=False,indent=1)
    for c in r['contests']: print(c['office'],'|',c['district'],'|',c['title'][:60],'|',c['jurisdiction'],'|',c['total_votes'],c.get('leading'),c['reporting']['reporting'],'/',c['reporting']['total'])
