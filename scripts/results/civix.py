import re,sys,json
from bs4 import BeautifulSoup
from lib import *
CFG={'NE':'https://electionresults.nebraska.gov','SD':'https://electionresults.sd.gov','MT':'https://electionresults.mt.gov','NM':'https://electionresults.sos.nm.gov','OR':'https://results.oregonvotes.gov'}
TZ={'NE':'CT','SD':'CT','MT':'MT','NM':'MT','OR':'PT'}
def parse_page(html):
    s=BeautifulSoup(html,'lxml')
    lines=[l for l in s.get_text('\n',strip=True).split('\n')]
    asof=None
    for i,l in enumerate(lines):
        if l.startswith('Results last updated'):
            asof=lines[i+1] if i+1<len(lines) and re.search(r'\d+/\d+/\d{4}',lines[i+1]) else re.sub(r'Results last updated:?\s*','',l); break
    out=[]; i=0
    while i<len(lines):
        l=lines[i]
        if l.startswith('Follow This Contest') and i>0:
            title=lines[i-1]; note=None
            if title.startswith('(') and i>1: note=title; title=lines[i-2]
            j=i+1; rep=None; 
            while j<len(lines) and not lines[j].startswith('Precincts') and j<i+12: j+=1
            if j<len(lines) and lines[j].startswith('Precincts'):
                m=re.match(r'Precincts Fully:\s*([\d,]+)\s*/\s*([\d,]+)',' '.join(lines[j:j+1]))
                if m: rep=(int(m.group(1).replace(',','')),int(m.group(2).replace(',','')))
                k=j+1
                while k<len(lines) and (lines[k]=='|' or lines[k].startswith('Partially')): k+=1
            else: k=i+1
            rows=[]
            while k<len(lines) and lines[k].lower()!='total votes':
                if k+2<len(lines) and re.fullmatch(r'[\d,]+',lines[k+2]) :
                    rows.append((re.sub(r'\s+',' ',lines[k]),lines[k+1],int(lines[k+2].replace(',','')))); k+=3
                elif k+1<len(lines) and re.fullmatch(r'[\d,]+',lines[k+1]):   # measure choice: label, votes
                    rows.append((re.sub(r'\s+',' ',lines[k]),None,int(lines[k+1].replace(',','')))); k+=2
                else: 
                    k+=1
                if k-i>400: break
            out.append((title,rep,rows,note))
            i=k
        i+=1
    return asof,out
def run(st,types=None):
    base=CFG[st]; ts=now()
    home=get(base+'/').text
    types=types or sorted(set(re.findall(r'resultsSW\.aspx\?type=([A-Z]+)&(?:amp;)?map=([A-Z]+)',home)))
    cs=[]; asof=None; seen=set(); alltitles=[]
    for t,mp in types:
        url=f'{base}/resultsSW.aspx?type={t}&map={mp}'
        r=get(url)
        a,items=parse_page(r.text); asof=asof or a
        for title,rep,rows,note in items:
            alltitles.append((t,title))
            title2=re.sub(r'^For ','',title)
            k=classify(title2)
            if not k and re.search(r'^(statewide|state)',t,re.I): pass
            if not k and is_measure_title(title2) and not re.search(r'county|city|school|district|bond',title2,re.I) and t in ('BM','SW','SB','IR','CA','ST','BQ'):
                k=('Ballot Measure',title2)
            if not k or (title,url) in seen: continue
            seen.add((title,url))
            cands=[{'name':n,'party':p,'votes':v,'write_in':bool(re.search('write',n,re.I))} for n,p,v in rows]
            desc=None
            if k[0]=='Ballot Measure' and ':' in title2:
                short,_,desc=title2.partition(':'); desc=desc.strip(); desc=desc.split(short)[0].strip() or desc; title2=short.strip(); k=('Ballot Measure',title2)
            cs.append(contest(k[0],k[1],title2,cands,url,ts,{'unit':'precincts fully reported','reporting':rep[0] if rep else None,'total':rep[1] if rep else None},asof,1))
            if desc: cs[-1]['description']=desc
            if note: cs[-1]['notes']='Source flags this contest: '+note+'.'
    return {'state':st,'election_date':'2026-11-03','source_url':base+'/','retrieved_at':ts,'results_as_of':asof+' ('+TZ[st]+')' if asof else None,'contests':cs,'_titles':alltitles,'_types':types}
if __name__=='__main__':
    for st in sys.argv[1:]:
        r=run(st); json.dump(r,open(f'out/{st}.raw.json','w'),ensure_ascii=False,indent=1)
        print(st,len(r['contests']),r['results_as_of'],r['_types'])
        for c in r['contests']: print('  ',c['office'],c['district'],c['title'][:60],'|',c['total_votes'],c.get('leading'),c['reporting'])
        print('  OTHER:',[t for t in r['_titles'] if not classify(re.sub(r'^For ','',t[1]))][:15])
