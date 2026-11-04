import re,json
from bs4 import BeautifulSoup
from lib import *
B='https://elections.maryland.gov/elections/2026/General_results/'
def iv(x):
    x=x.replace(',','').strip(); return int(x) if x.isdigit() else 0
def tbl(t):
    rows=[]
    for tr in t.find_all('tr')[1:]:
        td=[x.get_text(' ',strip=True) for x in tr.find_all(['td','th'])]
        if len(td)<8 or td[0].lower().startswith('total'): continue
        rows.append(td)
    return rows
def run():
    ts=now(); cs=[]; asof=None
    def page(u):
        nonlocal asof
        r=get(B+u); s=BeautifulSoup(r.text,'lxml'); t=s.get_text('\n',strip=True)
        m=re.search(r'Last refreshed:\s*(.+)',t)
        if m: asof=m.group(1).strip()+' (Eastern Time, per source)'
        m=re.search(r'\((\d+) of (\d+) election day precincts reported\)',t)
        rep={'unit':'election-day precincts','reporting':int(m.group(1)),'total':int(m.group(2))} if m else None
        return s,B+u,rep
    for u,off,title in [('gen_results_2026_1.html','Governor','Governor / Lt. Governor'),('gen_results_2026_2.html','Statewide Office','Comptroller'),('gen_results_2026_3.html','Statewide Office','Attorney General')]:
        s,src,rep=page(u); rows=tbl(s.find('table'))
        cands=[{'name':r[0],'party':r[1] or None,'votes':iv(r[6]),'write_in':'Write-In' in r[0]} for r in rows]
        c=contest(off,None,title,cands,src,ts,rep,asof,1); c['jurisdiction']='Statewide'; cs.append(c)
    s,src,rep=page('gen_results_2026_4.html')
    for t in s.find_all('table'):
        h=t.find_previous(string=re.compile(r'District\s+\d+'))
        d=re.search(r'District\s+(\d+)',h).group(1)
        rows=tbl(t); cands=[{'name':r[0],'party':r[1] or None,'votes':iv(r[6]),'write_in':'Write-In' in r[0]} for r in rows]
        pm=t.find_previous(string=re.compile(r'election day precincts reported')); mm=re.search(r'\((\d+) of (\d+)',pm) if pm else None
        rep=({'unit':'election-day precincts','reporting':int(mm.group(1)),'total':int(mm.group(2))} if mm else rep)
        cs.append(contest('US House',str(int(d)),f'Representative in Congress, District {d}',cands,src,ts,rep,asof,1))
    s,src,rep=page('gen_qresults_2026_1_00_ALL.html')
    for t in s.find_all('table'):
        h=t.find_previous(string=re.compile(r'Question\s+\d+:'))
        if not h: continue
        q=re.search(r'Question\s+(\d+)',h).group(1); head=h.strip()
        sub=[x.strip() for x in h.find_all_next(string=True,limit=8)] if False else []
        rows=[]
        for tr in t.find_all('tr')[1:]:
            td=[x.get_text(' ',strip=True) for x in tr.find_all(['td','th'])]
            if len(td)<7 or td[0].lower().startswith('total'): continue
            rows.append((td[0],iv(td[5])))
        cands=[{'name':re.sub(r'^(For|Against) the .*',lambda m:m.group(1),n),'party':None,'votes':v} for n,v in rows]
        # description lines between heading and table
        lines=[]
        for x in h.find_all_next(string=True):
            x=x.strip()
            if not x: continue
            if x.startswith('View Question') or x.startswith('County Break'): break
            if x!=head: lines.append(x)
        c=contest('Ballot Measure',f'Question {q}',head+(' — '+' '.join(lines) if lines else ''),cands,src,ts,rep,asof,1)
        c['jurisdiction']='Statewide'; c['description']=' '.join(lines) or None; cs.append(c)
    return {'state':'MD','election_date':'2026-11-03','source_url':'https://elections.maryland.gov/elections/2026/General_results/ElectionResultsDashboard.html','retrieved_at':ts,'results_as_of':asof,'contests':cs}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/MD.raw.json','w'),ensure_ascii=False,indent=1)
    for c in r['contests']: print(c['office'],c['district'],c['title'][:90],c['total_votes'],c.get('leading'),c.get('margin_votes'),c['reporting'])
