import re,json
from bs4 import BeautifulSoup
from lib import *
B='https://floridaelectionwatch.gov'
def parse(path):
    r=get(B+path); h=r.text
    s=BeautifulSoup(h,'lxml'); out=[]
    for t in s.find_all('table',style=re.compile('width:100%')):
        # candidate table
        if not t.find(class_='grid-head'): continue
        # find nearest preceding titleDescription
        d=t.find_previous(class_='titleDescription')
        title=re.sub(r'\s+',' ',d.get_text(' ',strip=True)) if d else ''
        card=t.find_previous(class_='contestHeader')
        rows=[]
        for tr in t.find_all('tr',class_='grid-row'):
            tds=tr.find_all('td')
            name=tds[0].get_text(' ',strip=True); party=tds[1].get_text(strip=True)
            votes=int(tds[2].get_text(strip=True).replace(',','')); 
            pb=tr.find(class_='progressbar'); cls=pb.get('class') if pb else []
            rows.append((name,party,votes,'winner' if 'winner' in cls else 'loser' if 'loser' in cls else None))
        tot=t.get_text(' ',strip=True)
        out.append((title,rows,B+path,card.get_text(strip=True) if card else ''))
    return out
def run():
    ts=now(); cs=[]
    for path in ['/FederalOffices/USSenator','/FederalOffices/USRepresentative','/StateOffices/Governor']:
        for title,rows,src,card in parse(path):
            c=classify(title)
            if not c: print('skip',title); continue
            cands=[{'name':n,'party':p,'votes':v,'write_in':p=='WRI','official_page_marker':m} for n,p,v,m in rows]
            cs.append(contest(c[0],c[1],title,cands,src,ts,None,None,1))
    # amendments
    r=get(B+'/Amendments'); s=BeautifulSoup(r.text,'lxml')
    for t in s.find_all('table',style=re.compile('width:100%')):
        if not t.find(class_='grid-head'): continue
        card=t.find_previous(class_='titleDescription'); title=re.sub(r'\s+',' ',card.get_text(' ',strip=True)) if card else ''
        # nearest amendment name
        blk=t.find_previous(string=re.compile(r'Amendment No\. ?\d+'))
        am=re.search(r'Amendment No\. ?\d+',blk).group(0) if blk else title
        desc=title
        rows=[]
        for tr in t.find_all('tr',class_='grid-row'):
            tds=tr.find_all('td'); rows.append((tds[0].get_text(' ',strip=True),tds[-3].get_text(strip=True) if False else None))
        rows=[]
        for tr in t.find_all('tr',class_='grid-row'):
            tds=tr.find_all('td'); nums=[x.get_text(strip=True).replace(',','') for x in tds[1:]]; v=next(int(x) for x in nums if x.isdigit()); rows.append((tds[0].get_text(' ',strip=True),v))
        cands=[{'name':n,'party':None,'votes':v} for n,v in rows]
        c=contest('Ballot Measure',am,f'{am}: {desc}' if desc and desc!=am else am,cands,B+'/Amendments',ts,None,None,1)
        c['notes']='Florida Election Watch states: "Amendments require 60% to pass."'
        cs.append(c)
    return {'state':'FL','election_date':'2026-11-03','source_url':B+'/','retrieved_at':ts,'results_as_of':None,'contests':cs}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/FL.raw.json','w'),ensure_ascii=False,indent=1)
    for c in r['contests']: print(c['office'],c['district'],c['title'][:70],c['total_votes'],c.get('leading'))
