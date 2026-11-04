import json,re
from lib import *
B='https://enr.indianavoters.in.gov/site/data/'
def run():
    ts=now()
    st=get(B+'settings.json').json()['Root']; el=get(B+'statewideElectionsC_B.json').json()['Root']
    tk=get(B+'statewideTickerC_B.json').json()['Root']
    jr=el.get('JurisdictionsReporting',{})
    rep={'unit':'precincts','reporting':int(jr['TOTAL_ALLPRECINCTSREPORTING']),'total':int(jr['TOTAL_ALLPRECINCTS'])}
    cs=[]
    for r in tk['ElectionSummaries']['Race']:
        title=r['OFFICE_TITLE']; k=classify(title)
        if not k: continue
        cands=[{'name':re.sub(r'\s*\(W/I\)','',c['NAME_ON_BALLOT']).strip(),'party':c['PARTY'],'votes':int(c['TOTAL']),'write_in':'(W/I)' in c['NAME_ON_BALLOT']} for c in r['Candidates']['Candidate']]
        cs.append(contest(k[0],k[1],title,cands,'https://enr.indianavoters.in.gov/',ts,rep,tk['WriteTime']+' (ET)',1))
    return {'state':'IN','election_date':'2026-11-03','source_url':'https://enr.indianavoters.in.gov/','retrieved_at':ts,'results_as_of':tk['WriteTime']+' (Indiana local time)','official_results_flag':st.get('Certified')=='T','contests':cs}
if __name__=='__main__':
    r=run(); json.dump(r,open('out/IN.raw.json','w'),ensure_ascii=False,indent=1)
    for c in r['contests']: print(c['office'],c['district'],c['title'],c['total_votes'],c['leading'])
