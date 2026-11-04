import re,json
from collections import OrderedDict
from lib import *
S='https://static.electionresults.vermont.gov/elections'
PAGE='https://electionresults.vermont.gov/'
def run():
    ts=now()
    els=get(S+'/elections.json').json()
    e=[x for x in els if x['electionName'].strip()=='2026 GENERAL ELECTION' and x['electionDate'].startswith('2026-11-03')][0]
    g=e['electionGuid']; meta=get(f'{S}/{g}.json').json()
    asof=meta.get('lastUpdatedDate'); tr=meta.get('townsReporting')
    m=re.match(r'(\d+)/(\d+)',tr or ''); rep={'unit':'towns','reporting':int(m.group(1)),'total':int(m.group(2))} if m else None
    cs=[]
    for key in ('federal','stateWide'):
        p=meta[key]['path'].replace('\\','/')
        d=get('https://static.electionresults.vermont.gov/'+p).json()
        for party in d['d']:
            for o in party['o']:
                tot={}; names={}; parties={}; blanks=0
                for row in o['cs']:
                    blanks+=row.get('bv') or 0
                    for c in row['rc']+row.get('wc',[]):
                        tot[c['cid']]=tot.get(c['cid'],0)+c['vc']; names[c['cid']]=c['cn'] or 'Write-in'; parties[c['cid']]=c.get('pn')
                cands=[{'name':names[k],'party':(parties[k] or '').title() or None,'votes':v,'write_in':'WRITE-IN' in names[k].upper()} for k,v in tot.items()]
                on=o['on'].title().replace(' Of ',' of ')
                if on=='Representative To Congress': off,dist,t=('US House','At-large','Representative to Congress (At-large)')
                elif on=='Governor': off,dist,t=('Governor',None,'Governor')
                else: off,dist,t=('Statewide Office',None,on)
                c=contest(off,dist,t,cands,PAGE,ts,rep,asof+' (Eastern Time, per source)',o.get('vf') or 1)
                c['blank_votes']=blanks or None
                if off!='US House': c['jurisdiction']='Statewide'
                c['pct_basis']='Share of votes for listed candidates and write-ins; blank votes excluded.'
                c['notes']=(c.get('notes','')+' Vermont reports by town; totals are the sum of the official town rows.').strip()
                cs.append(c)
    return {'state':'VT','election_date':'2026-11-03','source_url':PAGE,'retrieved_at':ts,'results_as_of':asof+' (Eastern Time, per source)','contests':cs}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/VT.raw.json','w'),ensure_ascii=False,indent=1)
    for c in r['contests']: print(c['office'],c['title'],c['total_votes'],c.get('leading'),c.get('margin_votes'),c['reporting'],[(x['name'],x['party'],x['votes']) for x in c['candidates'][:3]])
