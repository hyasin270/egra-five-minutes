"""Baseline: how long enumerators took per subtask and per child, from the SurveyCTO export.
Run: uv run --with openpyxl --with pandas python baseline_timings.py
"""
import openpyxl, pandas as pd, re, json, datetime as dt
wb=openpyxl.load_workbook('audio/EGRA_EGMA client N=2233.xlsx',read_only=True)
ws=wb['EGRA_EGMA client N=2233']
it=ws.iter_rows(values_only=True); hdr=[str(h) for h in next(it)]
df=pd.DataFrame(list(it),columns=hdr)
print('rows',len(df))
def to_dt(s):
    return pd.to_datetime(s,errors='coerce')
# whole-form duration
dur=pd.to_timedelta(df['duration'].astype(str),errors='coerce').dt.total_seconds()/60
print('\nWHOLE FORM duration (min): n=%d median=%.1f mean=%.1f p25=%.1f p75=%.1f p90=%.1f'%(dur.notna().sum(),dur.median(),dur.mean(),dur.quantile(.25),dur.quantile(.75),dur.quantile(.9)))
# per-subtask from start_/end_ pairs
pairs=[('listcomp_urd','start_listcomp_urd','end_listcomp_urd'),('letterid_urd','start_letterid_urd','end_letterid_urd'),('idwrd_urd','start_idwordrd_urd','end_idwordrd_urd'),
 ('orf_urd','start_orf_urd','start_rdcomp_urd'),('rdcomp_urd','start_rdcomp_urd','end_rdcomp_urd'),
 ('listcomp_eng','start_listcomp_eng','end_listcomp_eng'),('letterid_eng','start_letterid_eng','end_letterid_eng'),('pw_eng','start_psuedowrdrd_eng','end_psuedowrdrd_eng'),('idwrd_eng','start_idwordrd_eng','end_idwordrd_eng'),
 ('orf_eng','start_orf_eng','start_rdcomp_eng'),('rdcomp_eng','start_rdcomp_eng','end_rdcomp_eng'),
 ('idnummag','start_idnummag','end_idnummag'),('numrep','start_numrep','end_numrep'),('blfluency','start_blfluency','start_bleffcomp'),('bleffcomp','start_bleffcomp','end_bleffcomp'),('wrdpblm','start_wrdpblm','end_wrdpblm'),('patterns','start_patterns','end_patterns')]
out=[]
for name,a,b in pairs:
    s=to_dt(df[a]); e=to_dt(df[b]); d=(e-s).dt.total_seconds()
    d=d[(d>0)&(d<1800)]
    out.append(dict(subtask=name,n=int(d.count()),median_s=round(d.median(),0),mean_s=round(d.mean(),0),p25=round(d.quantile(.25),0),p75=round(d.quantile(.75),0),p90=round(d.quantile(.9),0)))
t=pd.DataFrame(out); print('\nPER-SUBTASK seconds (from start_/end_ timestamps):'); print(t.to_string(index=False))
print('\nSum of medians (s):',t.median_s.sum(), '=> %.1f min'%(t.median_s.sum()/60))
# language block totals
for lang,(a,b) in {'URDU block':('start_listcomp_urd','end_rdcomp_urd'),'ENGLISH block':('start_listcomp_eng','end_rdcomp_eng'),'MATH block':('start_idnummag','end_patterns')}.items():
    d=(to_dt(df[b])-to_dt(df[a])).dt.total_seconds()/60; d=d[(d>0)&(d<90)]
    print('%s: n=%d median=%.1f min mean=%.1f p75=%.1f p90=%.1f'%(lang,d.count(),d.median(),d.mean(),d.quantile(.75),d.quantile(.9)))
d=(to_dt(df['end_patterns'])-to_dt(df['start_listcomp_urd'])).dt.total_seconds()/60; d=d[(d>0)&(d<120)]
print('CHILD start-of-Urdu to end-of-math: n=%d median=%.1f mean=%.1f p75=%.1f p90=%.1f'%(d.count(),d.median(),d.mean(),d.quantile(.75),d.quantile(.9)))
# per child metadata
print('\nchild_age:',df['child_age'].value_counts().sort_index().to_dict())
print('class_grade_a:',df['class_grade_a'].value_counts().to_dict())
print('home_lang:',df['home_lang'].value_counts().head(8).to_dict())
print('enumerators:',df['enumerator'].nunique(),'schools:',df['emis_code'].nunique(),'dates:',df['today'].astype(str).str[:10].value_counts().sort_index().to_dict())
print('stu_present:',df['stu_present'].value_counts().to_dict(),'no_orf urd:',df['no_orf'].value_counts().to_dict(),'no_orf eng:',df['no_orf_eng'].value_counts().to_dict())
# score summaries
for c in ['lid_reading_score_urd','lid_reading_score_eng','idwrd_60s_correct_urd','idwrd_60s_correct_eng','orf_60s_correct_urd','orf_60s_correct_eng','pw_60s_correct_eng','listcomp_numcorrect_urd','rdcomp_numcorrect_urd','idnummag_numcorrect','comp_numcorrect','wrdpblm_numcorrect','patterns_numcorrect']:
    v=pd.to_numeric(df[c],errors='coerce'); print('%-28s n=%4d median=%5.1f mean=%5.1f zero=%d'%(c,v.notna().sum(),v.median(),v.mean(),(v==0).sum()))
t.to_csv('baseline_subtask_timings.csv',index=False)
df[['unique_id_calc','enumerator','emis_code','school_name','stu_code','stu_gender','child_age','class_grade_a','home_lang','duration','audio_comp','txt_audit']].to_csv('audio/_child_index.csv',index=False)
