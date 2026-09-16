"""Re-score the cached SpeechAce responses properly: per-word verdict (quality_score < 60 = wrong) vs the enumerator's
item flags on exactly the words SpeechAce scored (first ~29 s), plus count agreement on that same word range.
Also sweep the quality threshold. Run: uv run --with pandas python harness/09b_speechace_eval.py"""
import json,glob,os,pandas as pd
rows=[]; items=[]
for p in glob.glob('harness/english/speechace__*.json'):
    j=json.load(open(p)); f=os.path.basename(p).split('__')[1]; sub=os.path.basename(p).split('__')[2].replace('.json','')
    gtp='harness/gt/'+f
    if not os.path.exists(gtp) or 'text_score' not in j: continue
    gt=json.load(open(gtp)); flags=gt['items'].get(sub) or []; sc=gt['scores']
    pre='orf' if sub=='orf_eng' else 'idwrd'; e_att=sc.get(f'{pre}_60s_attempted_eng') or sc.get(f'{pre}_reading_attempted_eng')
    ws=j['text_score']['word_score_list']
    reach=min(len(ws), int(float(e_att)) if e_att not in (None,'') else len(ws), len(flags))
    pairs=[(w.get('quality_score') or 0, flags[i]) for i,w in enumerate(ws[:reach]) if flags[i] is not None]
    if not pairs: continue
    n=len(pairs); enum_c=sum(1 for q,fl in pairs if fl==0)
    for thr in (40,50,60,70):
        mc=sum(1 for q,fl in pairs if q>=thr)
        rows.append(dict(file=f[:12],sub=sub,thr=thr,n=n,enum_correct=enum_c,sa_correct=mc,agree=sum(1 for q,fl in pairs if (q<thr)==(fl==1))/n,
                         prec=(sum(1 for q,fl in pairs if q<thr and fl==1)/max(1,sum(1 for q,fl in pairs if q<thr))),rec=(sum(1 for q,fl in pairs if q<thr and fl==1)/max(1,sum(1 for q,fl in pairs if fl==1)))))
    items+=[dict(sub=sub,q=q,wrong=fl) for q,fl in pairs]
d=pd.DataFrame(rows)
for (sub,thr),g in d.groupby(['sub','thr']):
    diff=g.sa_correct-g.enum_correct
    print(f"speechace {sub:10s} thr={thr} n_children={len(g):3d} words/child={g.n.mean():.0f} count r={g.sa_correct.corr(g.enum_correct):.2f} MAE={diff.abs().mean():.1f} bias={diff.mean():+.1f} within±3={100*(diff.abs()<=3).mean():.0f}% | per-word agree={g.agree.mean():.2f} miscue prec={g.prec.mean():.2f} rec={g.rec.mean():.2f}")
it=pd.DataFrame(items); print('\nquality_score by enumerator verdict:'); print(it.groupby(['sub','wrong']).q.describe()[['count','mean','25%','50%','75%']].round(1))
