"""Harness step 1: Soniox stt-async-v3 (diarised, hints ur+en) over every recording → harness/soniox/<file>.json
Run: uv run --with requests python harness/01_soniox_batch.py   (idempotent; 4 workers)"""
import os, sys, requests, time, json, subprocess, concurrent.futures as cf
ROOT="/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
key=[l.split('=',1)[1].strip() for l in open(os.path.join(ROOT,'02_Main Rumi Bot/.env')) if l.startswith('SONIOX_API_KEY=')][-1]
H={'Authorization':f'Bearer {key}'}
def one(fn):
    out=f'harness/soniox/{fn}.json'
    if os.path.exists(out): return fn,'cached'
    src=f'audio/{fn}'; wav=f'harness/soniox/{fn}.wav'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',src,'-ar','16000','-ac','1',wav],check=True)
    try:
        f=requests.post('https://api.soniox.com/v1/files',headers=H,files={'file':open(wav,'rb')},timeout=300).json(); fid=f['id']
        t=requests.post('https://api.soniox.com/v1/transcriptions',headers=H,json={'file_id':fid,'model':'stt-async-v3','language_hints':['ur','en'],'enable_language_identification':True,'enable_speaker_diarization':True,'speaker_diarization_config':{'min_speakers':2,'max_speakers':4}},timeout=60).json(); tid=t['id']
        while True:
            s=requests.get(f'https://api.soniox.com/v1/transcriptions/{tid}',headers=H,timeout=60).json()
            if s['status'] in ('completed','error'): break
            time.sleep(3)
        if s['status']!='completed': return fn,'error:'+str(s.get('error_message'))[:100]
        tr=requests.get(f'https://api.soniox.com/v1/transcriptions/{tid}/transcript',headers=H,timeout=120).json()
        json.dump(tr,open(out,'w'),ensure_ascii=False)
        requests.delete(f'https://api.soniox.com/v1/transcriptions/{tid}',headers=H,timeout=30); requests.delete(f'https://api.soniox.com/v1/files/{fid}',headers=H,timeout=30)
        return fn,f"ok:{len(tr.get('tokens',[]))}tok"
    finally:
        if os.path.exists(wav): os.remove(wav)
files=sorted(f for f in os.listdir('audio') if f.endswith('.m4a'))
print(len(files),'files',flush=True)
with cf.ThreadPoolExecutor(4) as ex:
    for i,(fn,st) in enumerate(ex.map(one,files)): print(i+1,fn[:20],st,flush=True)
print('BATCH_DONE',flush=True)
