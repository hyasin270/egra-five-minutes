"""ffprobe every recording, join to the child index + coach reviews, write audio/_audio_index.csv and print baseline stats.
Run: uv run --with pandas python audio_durations.py"""
import subprocess, os, json, pandas as pd
rows=[]
for fn in sorted(os.listdir('audio')):
    if not fn.endswith('.m4a'): continue
    p=os.path.join('audio',fn)
    r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,bit_rate:stream=sample_rate,channels,codec_name','-of','json',p],capture_output=True,text=True)
    j=json.loads(r.stdout or '{}'); f=j.get('format',{}); s=(j.get('streams') or [{}])[0]
    rows.append(dict(audio_filename=fn,duration_s=float(f.get('duration',0)),bit_rate=int(f.get('bit_rate',0)),sample_rate=s.get('sample_rate'),channels=s.get('channels'),codec=s.get('codec_name'),size_bytes=os.path.getsize(p)))
a=pd.DataFrame(rows)
m=pd.read_csv('audio/_audio_to_child.csv').drop_duplicates('audio_filename')
a=a.merge(m,on='audio_filename',how='left')
ci=pd.read_csv('audio/_child_index.csv')
a=a.merge(ci[['unique_id_calc','enumerator','school_name','stu_gender','child_age','class_grade_a','home_lang','duration']].rename(columns={'duration':'form_duration'}),on='unique_id_calc',how='left')
a.to_csv('audio/_audio_index.csv',index=False)
d=a.duration_s/60
print('recordings',len(a),'with child match',a.unique_id_calc.notna().sum())
print('AUDIO minutes: median %.1f mean %.1f p10 %.1f p25 %.1f p75 %.1f p90 %.1f max %.1f total %.0f min'%(d.median(),d.mean(),d.quantile(.1),d.quantile(.25),d.quantile(.75),d.quantile(.9),d.max(),d.sum()))
print('codec',a.codec.value_counts().to_dict(),'sample_rate',a.sample_rate.value_counts().to_dict(),'bitrate median',a.bit_rate.median())
print('grade dist',a.class_grade_a.value_counts().sort_index().to_dict())
print('age dist',a.child_age.value_counts().sort_index().to_dict())
print('enumerators',a.enumerator.nunique(),'schools',a.school_name.nunique(),'reviewers',a.reviewer.value_counts().to_dict())
c=pd.to_numeric(a.overall_compliance_pct,errors='coerce'); print('coach compliance on these: median %.1f, flagged %s'%(c.median(),a.flagged.astype(str).value_counts().to_dict()))
print(a.groupby('class_grade_a').duration_s.median().round(0).to_dict())
