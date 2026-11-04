import re,json,datetime,requests
UA='Mozilla/5.0 (X11; Linux x86_64) WeThePeople-CivicBot/1.0'
def now(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
STATUS='Unofficial — not yet certified'
def get(u,**k):
    k.setdefault('timeout',60); h=k.pop('headers',{}); h.setdefault('User-Agent',UA)
    return requests.get(u,headers=h,**k)
ORD={w:i+1 for i,w in enumerate('first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth'.split())}
def classify(title,cat=''):
    """Return (office,district_or_title) for wave-1 contests, else None."""
    t=re.sub(r'\s+',' ',title.strip()); tl=t.lower()
    if re.search(r'state board|board of ed|regent|state senat|state rep|state house|assembly|house of delegates|lieutenant|\blt\.? gov|court|judge|justice|retention|county|city of|town of|school|mayor|council|commission|trustee|sheriff|clerk|treasurer|auditor|attorney|secretary of|comptroller|superintendent|supervisor',tl) and not re.search(r'u\.?s\.? (house|rep|senat)|united states (house|rep|senat)|u\.s\. (house|rep|senat)|^governor',tl):
        return None
    if re.search(r'(^|\b)(u\.?s\.?|united states)\.? senat|^senator$|^senate$',tl):
        return ('US Senate',None)
    if re.search(r'u\.?s\.? (house|rep)|united states (house|rep)|u\.s\. (house|rep)|rep(resentative)? (in|to) (the )?.{0,20}congress|congressional district|^congress|^representative in congress|^u\.s\. congress',tl):
        m=re.search(r'district\s*0*(\d+)|dist\.?\s*0*(\d+)|0*(\d+)(?:st|nd|rd|th) (?:congressional|district)|\bcd\s*0*(\d+)|\b0*(\d+)\s*$',t,re.I)
        d=next((g for g in (m.groups() if m else []) if g),None)
        if not d:
            mo=re.search(r'\b('+'|'.join(ORD)+r')\b',tl)
            if mo: d=str(ORD[mo.group(1)])
        return ('US House',str(int(d)) if d else 'At-large')
    if re.match(r'^governor',tl):
        return ('Governor',None)
    return None
MEASURE_RE=re.compile(r'amendment|proposition|constitutional|referendum|initiative|ballot (question|issue|measure)|\bquestion\b|\bmeasure\b|\bprop\b|bond',re.I)
def is_measure_title(t): return bool(MEASURE_RE.search(t))
def clean_name(n):
    n=re.sub(r'\s*\((I|Inc|Incumbent)\)',' ',n)
    n=re.sub(r'\s*\((Rep|Dem|Lib|Grn|Ind|Con|NPA|Una|REP|DEM|LIB|GRN|IND|CON|[A-Za-z]{2,4})\)\s*$','',n.strip())
    return re.sub(r'\s+',' ',n).strip()
def fixcase(n):
    if n!=n.upper() or len(n)<4: return n
    def w(x):
        if x=='AND': return 'and'
        if x in('II','III','IV','JR','JR.','SR','SR.'): return x.title() if x[0]!='I' else x
        if x.startswith('MC') and len(x)>2: return 'Mc'+x[2:].title()
        if x.startswith('O\'') and len(x)>2: return "O'"+x[2:].title()
        return x.title()
    return ' '.join('-'.join(w(p) for p in t.split('-')) for t in n.split(' '))
def finalize(cands,total_override=None):
    tot=sum(c['votes'] for c in cands)
    for c in cands: c['pct']=round(100*c['votes']/tot,2) if tot else None
    cands.sort(key=lambda c:-c['votes'])
    return tot
def contest(office,district,title,cands,src,ts,rep=None,asof=None,vote_for=1,notes=None,state=None):
    for c in cands: c['name']=fixcase(c['name'])
    tot=finalize(cands)
    for i,c in enumerate(cands): c['rank']=i+1
    d={'office':office,'district':district,'title':title,'vote_for':vote_for,'status':STATUS,
       'total_votes':tot,'candidates':cands,'reporting':rep,'results_as_of':asof,'source_url':src,'retrieved_at':ts}
    if vote_for and vote_for>1:
        d['notes']=f'Vote for up to {vote_for}. Candidates are listed by votes; "margin" is not computed for multi-seat contests.'
    elif len(cands)>=2 and tot>0:
        d['leading']=cands[0]['name'] if cands[0]['votes']>cands[1]['votes'] else None
        d['margin_votes']=cands[0]['votes']-cands[1]['votes']
        d['margin_pct']=round(cands[0]['pct']-cands[1]['pct'],2)
    elif len(cands)==1:
        d['leading']=cands[0]['name'] if cands[0]['votes']>0 else None
        d['notes']='Unopposed or single candidate on official feed.'
    if notes: d['notes']=(d.get('notes')+' ' if d.get('notes') else '')+notes
    return d
