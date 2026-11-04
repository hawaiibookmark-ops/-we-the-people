import re,json
from bs4 import BeautifulSoup
from lib import *
B='https://results.oregonvotes.gov'
def parse(html):
    lines=BeautifulSoup(html,'lxml').get_text('\n',strip=True).split('\n'); asof=None; out=[]
    for i,l in enumerate(lines):
        if l.startswith('Results last updated'): asof=re.sub(r'Results last updated:\s*','',l)
    i=0
    while i<len(lines):
        if lines[i]=='Follow this contest' and i>0:
            title=lines[i-1]; j=i+1
            while j<len(lines) and lines[j]!='total votes' and not lines[j].startswith('for ') : 
                j+=1
                if j-i>200: break
            seg=lines[i+1:j]
            # drop Export / EXPORT: / precinct line
            seg=[x for x in seg if x not in('Export','EXPORT:') and not re.match(r'\d+ out of \d+ Precincts',x)]
            rows=[]; k=0
            while k<len(seg):
                if k+2<len(seg) and re.fullmatch(r'[\d,]+',seg[k+2]) and not re.fullmatch(r'[\d,]+',seg[k+1]): rows.append((seg[k],seg[k+1],int(seg[k+2].replace(',','')))); k+=3
                elif k+1<len(seg) and re.fullmatch(r'[\d,]+',seg[k+1]): rows.append((seg[k],None,int(seg[k+1].replace(',','')))); k+=2
                else: k+=1
            out.append((title,rows)); i=j
        i+=1
    return asof,out
def run():
    ts=now(); cs=[]; asof=None; seen=set(); titles=[]
    home=get(B+'/').text
    types=sorted(set(re.findall(r'resultsSW\.aspx\?type=([A-Z]+)&(?:amp;)?map=([A-Z]+)',home)))
    for t,mp in types:
        if t in('MCR','LMEA','HOUSE','SENATE'): continue   # local / legislative handled in later waves
        url=f'{B}/resultsSW.aspx?type={t}&map={mp}'; a,items=parse(get(url).text); asof=asof or a
        for title,rows in items:
            titles.append((t,title)); k=classify(title)
            if title.startswith('US Senator'): k=('US Senate',None)
            m=re.match(r'US Representative, (\d+)',title)
            if m: k=('US House',str(int(m.group(1))))
            if title=='Governor': k=('Governor',None)
            if not k and t in('SWPAR','SWNON') and re.match(r'(Secretary of State|State Treasurer|Attorney General|Commissioner of|Superintendent|Labor)',title,re.I): k=('Statewide Office',None)
            if not k and re.search(r'measure|amendment|referral|initiative',title,re.I) and not re.search(r'county|city|district',title,re.I): k=('Ballot Measure',title)
            if not k or (title,url) in seen: continue
            seen.add((title,url))
            cands=[{'name':n,'party':p,'votes':v,'write_in':n.lower().startswith('write')} for n,p,v in rows]
            c=contest(k[0],k[1],title,cands,url,ts,None,asof,1)
            c['notes']='Oregon counts ballots by county; the source page shows "0 out of N precincts reported" for every contest, so no precinct-reporting figure is given here.'
            if k[0] in('US Senate','Governor','Statewide Office','Ballot Measure'): c['jurisdiction']='Statewide'
            cs.append(c)
    return {'state':'OR','election_date':'2026-11-03','source_url':B+'/','retrieved_at':ts,'results_as_of':(asof or '')+' (Pacific Time, per source)','contests':cs,'_titles':titles}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/OR.raw.json','w'),ensure_ascii=False,indent=1)
    for c in r['contests']: print(c['office'],c['district'],c['title'][:60],c['total_votes'],c.get('leading'),c.get('margin_votes'))
    print([t for t in r['_titles']][:40])
