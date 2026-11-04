import re,json,time,os,hashlib
from bs4 import BeautifulSoup
from lib import *
B='https://electionresults.sos.mn.gov'
PAGES=[('/Results/Index?ersElectionId=201&scenario=USSenate&officeInElectionIdList=38485&officeInElectionIdList=-1',None),
 ('/Results/Index?ersElectionId=201&scenario=USRepresentative',None),
 ('/Results/Index?ersElectionId=201&scenario=Governor&officeInElectionId=38695',None),
 ('/Results/Index?ersElectionId=201&scenario=SecretaryOfState&officeInElectionId=38696','Secretary of State'),
 ('/Results/Index?ersElectionId=201&scenario=StateAuditor&officeInElectionId=38697','State Auditor'),
 ('/Results/Index?ersElectionId=201&scenario=AttorneyGeneral&officeInElectionId=38698','Attorney General'),
 ('/Results/AmendmentResultsStatewide?ersElectionId=201&scenario=state','MEASURE')]
def fetch(url):
    f='raw/mn_'+hashlib.md5(url.encode()).hexdigest()[:10]+'.html'
    if os.path.exists(f) and 'think that you are a bot' not in open(f).read() and os.environ.get('FRESH')!='1': return open(f).read()
    for i in range(4):
        time.sleep(6); h=fetch(url)
        if 'think that you are a bot' not in h: open(f,'w').write(h); return h
        time.sleep(30)
    raise SystemExit('MN blocked automated access (bot challenge); not bypassing')
def run():
    ts=now(); cs=[]; asof=None
    for path,kind in PAGES:
        url=B+path; h=fetch(url)
        m=re.search(r'Last Updated:\s*(?:&nbsp;|\s)*([\d/]+ [\d:]+ [AP]M)',h)
        if m and not asof: asof=m.group(1)+' (Central Time, per source)'
        s=BeautifulSoup(h,'lxml')
        mp=re.search(r'Precincts Reporting in State:(?:&nbsp;|\s)*\d+%(?:&nbsp;|\s)*([\d,]+)(?:&nbsp;|\s)*of(?:&nbsp;|\s)*([\d,]+)',h); pr=(int(mp.group(1).replace(',','')),int(mp.group(2).replace(',',''))) if mp else None
        for t in s.find_all('table'):
            cap=t.find('caption')
            if kind=='MEASURE':
                txt=re.sub(r'\s+',' ',t.get_text(' ',strip=True)); mm=re.match(r'(CONSTITUTIONAL AMENDMENT \d+) Show Question (.*?) Shall (.*?\?) Yes ([\d,]+) No ([\d,]+)',txt)
                if not mm: continue
                title=mm.group(1).title()+': '+mm.group(2)
                cands=[{'name':'Yes','party':None,'votes':int(mm.group(4).replace(',',''))},{'name':'No','party':None,'votes':int(mm.group(5).replace(',',''))}]
                c=contest('Ballot Measure',mm.group(1).title(),title,cands,url,ts,{'unit':'precincts','reporting':pr[0],'total':pr[1]} if pr else None,asof,1)
                c['description']='Shall '+mm.group(3); c['jurisdiction']='Statewide'
                c['notes']='Minnesota counts only Yes and No votes cast on the question in this table; the official page also shows estimated blanks and an estimated percent of YES that uses all voters as the base.'
                cs.append(c); continue
            if cap:
                sp=cap.find('span',class_='boldFont'); title=re.sub(r'\s+',' ',sp.get_text(' ',strip=True)) if sp else ''
                rt=re.search(r'([\d,]+) precincts in contest\. ([\d,]+) of ([\d,]+) precincts reported',cap.get_text(' ',strip=True))
            else:
                title=kind or ''; rt=None
                if not kind or not t.find('tbody'): continue
            rep={'unit':'precincts','reporting':int(rt.group(2).replace(',','')),'total':int(rt.group(3).replace(',',''))} if rt else ({'unit':'precincts','reporting':pr[0],'total':pr[1]} if pr else None)
            rows=[]
            for tr in t.find('tbody').find_all('tr'):
                td=[x.get_text(' ',strip=True).replace('\xa0',' ') for x in tr.find_all('td')]
                if len(td)<5: continue
                rows.append((td[0],td[2],td[3]))
            if not rows: continue
            def iv(x): return int(re.sub(r'\D','',x) or 0)
            if kind=='MEASURE':
                cands=[{'name':n,'party':None,'votes':iv(v)} for p,n,v in rows if n]
                c=contest('Ballot Measure',title,title,cands,url,ts,rep,asof,1)
                c['jurisdiction']='Statewide'
                cs.append(c); continue
            cands=[]
            for p,n,v in rows:
                if not n or n.lower().startswith('total') : continue
                cands.append({'name':n,'party':p or None,'votes':iv(v),'write_in':bool(re.search('write-?in',n,re.I))})
            wi=[c for c in cands if re.match(r'write-?in',c['name'],re.I)]
            cl=classify(title) if kind is None else (kind,None)
            if not cl: print('skip',title); continue
            cs.append(contest(cl[0] if kind is None else 'Statewide Office',cl[1] if kind is None else None,title,cands,url,ts,rep,asof,1))
            cs[-1]['jurisdiction']='Statewide'
    return {'state':'MN','election_date':'2026-11-03','source_url':B+'/','retrieved_at':ts,'results_as_of':asof,'contests':cs}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/MN.raw.json','w'),ensure_ascii=False,indent=1)
    for c in r['contests']: print(c['office'],c['district'],c['title'][:60],c['total_votes'],c.get('leading'),c.get('margin_votes'),c['reporting'])
