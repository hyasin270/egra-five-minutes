"""Harness step 5: the human floor. For every subtask, how often did the QA reviewer (second human, re-listening
to the recording) agree with the enumerator's score? Uses the 1,462 QA rows; verdict per score field is
correct / incorrect / unknown. Also per-field agreement and the flagged rate.
Run: uv run --with pandas python harness/05_human_floor.py"""
import pandas as pd, json, collections
qa=pd.read_csv('audio/_coach_reviews.csv')
qa=qa[qa.instrument.fillna('')!='aser']  # EGRA/EGMA instrument reviews (labelled + unlabelled pre-June rows)
sub=collections.defaultdict(collections.Counter); field=collections.defaultdict(collections.Counter); proto=collections.Counter()
for v in qa.verdicts_json.dropna():
    try: j=json.loads(v)
    except: continue
    for s,items in j.items():
        if not isinstance(items,dict): continue
        if s.startswith('aser'): continue
        for k,val in items.items():
            if k=='__protocol_followed': proto[(s,str(val))]+=1; continue
            if k.startswith('__'): continue
            sub[s][str(val)]+=1; field[(s,k)][str(val)]+=1
rows=[]
for s,c in sorted(sub.items()):
    n=sum(c.values()); rows.append(dict(subtask=s,n_verdicts=n,agree=c['correct'],disagree=c['incorrect'],unknown=c['unknown'],agree_pct=round(100*c['correct']/n,1),disagree_pct=round(100*c['incorrect']/n,1),unknown_pct=round(100*c['unknown']/n,1),protocol_ok_pct=round(100*proto[(s,'True')]/max(1,proto[(s,'True')]+proto[(s,'False')]),1)))
df=pd.DataFrame(rows); print(df.to_string(index=False)); df.to_csv('harness/human_floor.csv',index=False)
print('\nreviews used',len(qa),'flagged',qa.flagged.astype(str).value_counts().to_dict(),'compliance median',pd.to_numeric(qa.overall_compliance_pct,errors='coerce').median())
print('\nOVERALL reading timed fields (letters/words/orf correct+attempted): agree %.1f%% disagree %.1f%% unknown %.1f%%'%tuple(100*x/sum(sum(field[k].values()) for k in field if any(t in k[1] for t in ('lid_','idwrd_','orf_','pw_'))) for x in (sum(field[k]['correct'] for k in field if any(t in k[1] for t in ('lid_','idwrd_','orf_','pw_'))),sum(field[k]['incorrect'] for k in field if any(t in k[1] for t in ('lid_','idwrd_','orf_','pw_'))),sum(field[k]['unknown'] for k in field if any(t in k[1] for t in ('lid_','idwrd_','orf_','pw_'))))))
