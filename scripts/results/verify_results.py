import json,glob,sys,os
root=sys.argv[1] if len(sys.argv)>1 else 'public/data/results'
idx=json.load(open(f'{root}/index.json')); bad=[]; n=0
assert len(idx['states'])==50
for e in idx['states']:
    d=json.load(open(f"{root}/{e['file']}"))
    if d['results_status']=='pending':
        if not d.get('source_url') or not d.get('pending_reason'): bad.append((e['state'],'pending missing link/reason'))
        continue
    for c in d['contests']:
        n+=1
        for k in('source_url','retrieved_at','status','office','title','candidates'):
            if not c.get(k): bad.append((e['state'],c.get('id'),'missing '+k))
        if c['status']!='Unofficial — not yet certified': bad.append((e['state'],c['id'],'status'))
        if any((x.get('votes') is None or x['votes']<0) for x in c['candidates']): bad.append((e['state'],c['id'],'votes'))
        s=json.dumps(c)
        if 'TAI' in s.split(): bad.append((e['state'],c['id'],'TAI'))
print('states',idx['counts'],'contests',n,'problems',len(bad)); [print(b) for b in bad[:20]]
sys.exit(1 if bad else 0)
