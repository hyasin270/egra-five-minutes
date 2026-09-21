"""Probe 2: our production STT (Soniox stt-async-v3, Urdu hint, diarization) on the Urdu letter-ID slice. Run: uv run --with requests python probe2_soniox.py <wav> <lang>"""
import os, sys, requests, time, json
ROOT="/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
key=[l.split('=',1)[1].strip() for l in open(os.path.join(ROOT,'02_Main Rumi Bot/.env')) if l.startswith('SONIOX_API_KEY=')][-1]
wav,lang=sys.argv[1],sys.argv[2]; H={'Authorization':f'Bearer {key}'}
f=requests.post('https://api.soniox.com/v1/files',headers=H,files={'file':open(wav,'rb')}).json(); fid=f['id']
t=requests.post('https://api.soniox.com/v1/transcriptions',headers=H,json={'file_id':fid,'model':'stt-async-v3','language_hints':[lang],'enable_language_identification':True,'enable_speaker_diarization':True,'speaker_diarization_config':{'min_speakers':2,'max_speakers':3}}).json(); tid=t['id']
t0=time.time()
while True:
    s=requests.get(f'https://api.soniox.com/v1/transcriptions/{tid}',headers=H).json()
    if s['status'] in ('completed','error'): break
    time.sleep(2)
print('status',s['status'],'elapsed %.0fs'%(time.time()-t0))
tr=requests.get(f'https://api.soniox.com/v1/transcriptions/{tid}/transcript',headers=H).json()
toks=tr.get('tokens',[]); print('tokens',len(toks))
out=[]; cur=None
for tk in toks:
    sp=tk.get('speaker'); 
    if sp!=cur: out.append(f"\n[{tk.get('start_ms',0)/1000:.1f}s spk{sp}] "); cur=sp
    out.append(tk['text'])
txt=''.join(out); print(txt[:3000])
json.dump(tr,open(f'probe2_soniox_{os.path.basename(wav)}.json','w'),ensure_ascii=False)
open(f'probe2_soniox_{os.path.basename(wav)}.md','w').write(f"# Probe 2 — Soniox stt-async-v3 on {wav} ({lang})\n\n{txt}")
