"""Probe 1: can an audio LLM segment an enumerator EGRA session into subtasks and extract the child's responses?
Sends the whole 17-min recording (8kHz source, upsampled) to Gemini via OpenRouter. Run: uv run --with requests python probe1_segment.py <model>"""
import os, sys, base64, json, requests, time
ROOT="/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
key=[l.split('=',1)[1].strip() for l in open(os.path.join(ROOT,'.env')) if l.startswith('NIETE_STAGING_OPENROUTER_API_KEY=')][-1]
model=sys.argv[1] if len(sys.argv)>1 else 'google/gemini-2.5-pro'
b64=base64.b64encode(open('probe1_full.mp3','rb').read()).decode()
PROMPT="""This is a ~17-minute recording of a trained enumerator in Rawalpindi, Pakistan administering an EGRA/EGMA battery to one Grade-3 child (age 10). The battery, in order, is usually:
URDU: listening comprehension (story read aloud twice, 6 questions) → letter identification (100 letters, 60s timed) → familiar word reading (50 words, 60s) → oral passage reading (60s) → reading comprehension (6 questions).
ENGLISH: listening comprehension → letter identification (60s) → pseudoword decoding (60s) → familiar word reading (60s) → passage reading (60s) → reading comprehension.
MATH: number identification → number comparison → timed addition/subtraction grids (60s each) → computation → word problems → patterns.
Tasks:
1. Segment the recording: for every subtask you can detect, give start and end time (mm:ss), language, and how you recognised it (instruction phrases you heard, in the original language).
2. For the Urdu letter identification and Urdu familiar-word subtasks, transcribe exactly what the child said, item by item, in Urdu script, and mark each item you believe the enumerator counted as correct/incorrect, with your own confidence 0-1.
3. For every math item you can hear, give the question as asked and the child's answer.
4. List every protocol deviation you notice (enumerator prompting, correcting, re-reading, background noise, class interruptions), with timestamps.
5. State the audio-quality limits you hit (this is 8 kHz audio-audit quality).
Return JSON with keys: segments[], urdu_letters[], urdu_words[], math_items[], deviations[], quality_notes, overall_confidence."""
t=time.time()
r=requests.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},
 json={'model':model,'messages':[{'role':'user','content':[{'type':'text','text':PROMPT},{'type':'input_audio','input_audio':{'data':b64,'format':'mp3'}}]}],'max_tokens':16000},timeout=900)
el=time.time()-t
j=r.json(); print('status',r.status_code,'elapsed %.0fs'%el)
if 'error' in j: print(j['error']); sys.exit(1)
txt=j['choices'][0]['message']['content']; print('usage',j.get('usage'))
open(f'probe1_{model.replace("/","_")}.md','w').write(f"# Probe 1 — {model} — elapsed {el:.0f}s — usage {j.get('usage')}\n\n{txt}")
print(txt[:6000])
