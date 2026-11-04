import re,json,subprocess,os,sys
from bs4 import BeautifulSoup
from lib import *
SRC='https://nyenr.elections.ny.gov/HomeNoJS.aspx'
NOTE_W='New York State Board of Elections states on this page: "these results do not include a significant number of unscanned emergency Election Day ballots from Westchester County. Accordingly, the results are incomplete and are subject to change as additional ballots are scanned and tabulated."'
def iv(x):
    x=re.sub(r'[^\d]','',x); return int(x) if x else 0
def run(refresh=False):
    if refresh or not os.path.exists('raw/ny2_0.html'):
        subprocess.run([sys.executable,'pwnav.py','ny2',SRC],check=True)
    h=open('raw/ny2_0.html').read(); s=BeautifulSoup(h,'lxml'); ts=now()
    m=re.search(r'(\d\d/\d\d/\d{4} \d\d:\d\d:\d\d [AP]M)',s.find(id='lblDateTime').get_text()) if s.find(id='lblDateTime') else None
    asof=(m.group(1)+' (Eastern Time, per source)') if m else None
    cs=[]
    for t in s.find_all('table',summary=re.compile('^Results for All Counties')):
        title=re.sub(r'^Results for All Counties\s*','',t['summary']).strip()
        hd=t.find('td',class_='resultsHeaderRight'); rm=re.search(r'Districts Reporting:\s*([\d,]+) of ([\d,]+)',hd.get_text()) if hd else None
        rep={'unit':'election districts','reporting':iv(rm.group(1)),'total':iv(rm.group(2))} if rm else None
        cands=[]; cur=None
        for tr in t.find_all('tr'):
            tds=tr.find_all('td',recursive=False)
            if not tds or tr.find('th'): continue
            if 'resultsHeaderWrap' in (tds[0].get('class') or []): continue
            first=tds[0].get_text(' ',strip=True)
            if tds[0].get('rowspan') is not None or (len(tds)>=8 and 'resultsColumnData' in (tds[0].get('class') or []) and len(tds)==8):
                votes=iv(tds[7].get_text()); name=re.sub(r'\s+',' ',first)
                cur={'name':name,'party':tds[1].get_text(strip=True) or None,'votes':votes,'party_lines':[tds[1].get_text(strip=True)]}
                if name.lower() in('blank','void','scattering'): cur['_skip']=True
                cands.append(cur)
            elif cur is not None and len(tds)>=1:
                cur['party_lines'].append(first)
        blanks=[c for c in cands if c.pop('_skip',None)]
        cands=[c for c in cands if c not in blanks]
        for c in cands:
            c['write_in']=c['name'].lower().startswith('write')
            c['party_lines']=[p for p in c['party_lines'] if p]
            if len(c['party_lines'])>1: c['party']='/'.join(c['party_lines'])
            c.pop('party_lines')
        mo=re.search(r'(\d+)(?:st|nd|rd|th)\s+(Congressional|Senate|Assembly|Judicial)\s+District',title)
        if title=='Governor and Lieutenant Governor': off,dist,tt='Governor',None,'Governor and Lieutenant Governor'
        elif title in('State Comptroller','Attorney General'): off,dist,tt='Statewide Office',None,title
        elif mo and mo.group(2)=='Congressional': off,dist,tt='US House',str(int(mo.group(1))),f'Representative in Congress, District {int(mo.group(1))}'
        elif mo and mo.group(2)=='Senate': off,dist,tt='State Senate',str(int(mo.group(1))),title
        elif mo and mo.group(2)=='Assembly': off,dist,tt='State House',str(int(mo.group(1))),title+' (State Assembly)'
        else: continue
        c=contest(off,dist,tt,cands,SRC,ts,rep,asof,1)
        c['blank_votes']=sum(b['votes'] for b in blanks) or None
        c['pct_basis']='Share of votes for listed candidates; blank, void and scattering votes excluded. The source page includes them in its percentages.'
        c['notes']=NOTE_W; c['jurisdiction']='Statewide' if off in('Governor','Statewide Office') else None
        cs.append(c)
    return {'state':'NY','election_date':'2026-11-03','source_url':SRC,'retrieved_at':ts,'results_as_of':asof,'contests':cs,'notes':NOTE_W}
if __name__=='__main__':
    r=run('--refresh' in sys.argv); json.dump(r,open('out/NY.raw.json','w'),ensure_ascii=False,indent=1)
    from collections import Counter
    print(Counter(c['office'] for c in r['contests']))
    for c in r['contests'][:6]+r['contests'][-2:]: print(c['office'],c['district'],c['title'],c['total_votes'],c['leading'],c['margin_votes'],c['reporting'],[ (x['name'],x['party'],x['votes']) for x in c['candidates']][:3])
