"""Harness step 15: write the ONE canonical evaluation record (harness/HARNESS_RESULTS.md) from every cached result,
merging what was earlier called round 1 and round 2 into a single document: method, human floor, one table per task
with every scorer we tried, the worked examples, and the stack we recommend. No round-by-round ledger.
Run: uv run --with pandas python harness/15_evaluation_doc.py
"""
import os, json, glob
import pandas as pd

FLOOR = {r['subtask']: r for r in pd.read_csv('harness/human_floor.csv').to_dict('records')}
NICE = {'google/gemini-3.1-pro-preview': 'Gemini 3.1 Pro', 'google/gemini-3.8-flash': 'Gemini 3.8 Flash', 'google/gemini-3.5-flash-lite': 'Gemini 3.5 Flash-Lite', 'google/gemini-2.5-flash': 'Gemini 2.5 Flash',
        'openai/gpt-audio': 'GPT audio', 'openai/gpt-audio-mini': 'GPT audio mini', 'xiaomi/mimo-v2.5': 'MiMo 2.5', 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': 'Nemotron omni (free)', 'mistralai/voxtral-small-24b-2507': 'Voxtral small',
        'anthropic/claude-sonnet-5': 'Claude Sonnet 5', 'openai/gpt-5-mini': 'GPT-5 mini', 'google/gemini-3-flash-preview': 'Gemini 3 Flash', 'deepseek/deepseek-v3.2': 'DeepSeek 3.2', 'google/gemini-2.5-flash-lite': 'Gemini 2.5 Flash-Lite',
        'anthropic/claude-haiku-4.5': 'Claude Haiku 4.5', 'google/gemini-2.5-pro': 'Gemini 2.5 Pro'}
SUBN = {'orf_urd': 'Urdu story (60 s)', 'orf_eng': 'English story (60 s)', 'idwrd_urd': 'Urdu word list (60 s)', 'idwrd_eng': 'English word list (60 s)', 'pw_eng': 'English pseudowords (60 s)', 'letterid_urd': 'Urdu letters (60 s)', 'letterid_eng': 'English letters (60 s)'}
FLOORKEY = {'orf_urd': 'orf_urd', 'orf_eng': 'orf_eng', 'idwrd_urd': 'idwrd_urd', 'idwrd_eng': 'idwrd_eng', 'pw_eng': 'pw_eng', 'letterid_urd': 'letterid_urd', 'letterid_eng': 'letterid_eng', 'rdcomp_urd': 'rdcomp_urd', 'wrdpblm': 'word_problems', 'bleffcomp': 'computation', 'idnummag': 'idnummag', 'numrep': 'numrep', 'patterns': 'patterns'}

def floor(sub):
    f = FLOOR.get(FLOORKEY.get(sub, sub)); return f"{f['agree_pct']:.0f}%" if f else '—'

def spend():
    tot = 0
    for pat in ['harness/windows/*.json', 'harness/comprehension/*.json', 'harness/segments_llm/*.json', 'harness/maths/*.json', 'harness/reference/*.json']:
        for p in glob.glob(pat):
            try: tot += json.load(open(p)).get('cost') or 0
            except Exception: pass
    wmin = sum(json.load(open(p)).get('minutes', 0) for p in glob.glob('harness/whisper_en/*.json'))
    return tot, wmin

O = []
tot, wmin = spend()
O += ['# The evaluation: every scorer we tried, beside the humans', '',
      f'**Data:** 187 enumerator recordings from the May 2026 Rawalpindi EGRA/EGMA study that join to a child\'s tablet scores and a reviewer\'s re-listen; 8 kHz classroom audio. **Scripts:** `harness/01…15` (numbered for reproduction; every model reply is cached). **Model spend for the whole evaluation:** ≈ ${tot + wmin * 0.006 + 8.5:.0f} (LLMs through OpenRouter ${tot:.2f}, whisper-1 ${wmin * 0.006:.2f}, Soniox ≈ $8.50; SpeechAce on the existing plan; Azure unavailable).', '',
      '## 1. How a score is judged', '',
      '- **Primary human:** the enumerator\'s live tablet marks: per-item right/wrong flags up to the word reached, the 60-second counts, comprehension and maths items.',
      '- **Second human (the floor):** a QA reviewer re-listened to the recording and marked whether each enumerator score was right. How often the two humans agree is the realistic ceiling for any scorer on this audio; it is printed beside every model number.',
      '- **Counts:** correlation (r), mean absolute error in words (MAE), bias (machine minus enumerator), and the share of children within ±5 words.',
      '- **Per-word marks:** compared only on words both the enumerator and the scorer reached (the export writes 0 for both "correct" and "never reached"). Precision = of the words the scorer flagged wrong, the share the enumerator also marked wrong; recall = of the enumerator\'s wrong words, the share the scorer caught.',
      '- **Baseline:** speech-to-text (Soniox for Urdu, whisper-1 forced to English) plus spelling alignment to the printed text, on the very same windows.',
      '- **Worked examples:** twelve real windows with every artefact (printed text, clip, transcript, every scorer\'s per-word verdicts) are in `harness/examples/` and on the site.', '']

# ---- human floor table
O += ['## 2. The human floor', '', '| Subtask | Reviewer agreed with enumerator | Disagreed | Could not tell |', '|---|---:|---:|---:|']
for k in ['letterid_urd', 'letterid_eng', 'idwrd_urd', 'idwrd_eng', 'pw_eng', 'orf_urd', 'orf_eng', 'listcomp_urd', 'rdcomp_urd', 'idnummag', 'numrep', 'computation', 'word_problems', 'patterns', 'blfluency_l1']:
    f = FLOOR.get(k)
    if f: O.append(f"| {k} | {f['agree_pct']:.0f}% | {f['disagree_pct']:.0f}% | {f['unknown_pct']:.0f}% |")
O += ['', 'On the timed word lists and stories two trained humans agree only about half the time on this audio; on letters and maths about nine times in ten. That is the bar.', '']

# ---- reading windows: baseline (all files) + every model
rs = pd.read_csv('harness/reading_summary.csv')
O += ['## 3. Reading windows: counts and per-word marks', '', '### 3a. The baseline on every recording (speech-to-text + alignment)', '',
      '| Subtask | n | wrong-window cases | on the rest: r | MAE | bias | within ±5 | human floor |', '|---|---:|---:|---:|---:|---:|---:|---:|']
for r in rs.to_dict('records'):
    O.append(f"| {SUBN.get(r['subtask'], r['subtask'])} | {r['n']} | {r['window_fail_pct']}% | {r['r']} | {r['MAE']} | {r['bias']:+} | {r['within5']}% | {floor(r['subtask'])} |")
O += ['', '"Wrong-window cases" are recordings where the segmenter cut the wrong part of the 20-minute session (|error| > 20 words); the product design removes them (one voice note per block). Letters fail for the machine as they nearly fail for the reviewer\'s ear: letter names came back in three scripts.', '']
w = pd.read_csv('harness/window_scores.csv').dropna(subset=['machine_correct', 'enum_correct']).copy(); w['enum_correct'] = pd.to_numeric(w.enum_correct)
O += ['### 3b. Every scorer on the same sixty-second windows, with the printed text supplied', '',
      'Audio scorers heard the clip; transcript scorers read the STT transcript of it; every scorer saw the exact printed text and returned a verdict per word. Baseline = alignment on the very same windows. Sorted by MAE within each subtask.', '']
for sub in ['orf_urd', 'idwrd_urd', 'orf_eng']:
    O += [f'**{SUBN[sub]}** — human floor {floor(sub)}', '', '| Scorer | input | n | count r | MAE | bias | within ±5 | word precision | word recall | $/window |', '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    rows = []
    g0 = w[w['sub'] == sub]
    gb = g0.drop_duplicates(['file', 'sub'])
    if len(gb):
        bd = gb.baseline_correct - gb.enum_correct
        rows.append(('Baseline: STT + alignment', 'transcript', len(gb), gb.baseline_correct.corr(gb.enum_correct), bd.abs().mean(), bd.mean(), 100 * (bd.abs() <= 5).mean(), None, None, 0.0))
    for (arm, model), g in g0.groupby(['arm', 'model']):
        d = g.machine_correct - g.enum_correct
        prec = g.tp.sum() / max(1, g.tp.sum() + g.fp.sum()); rec = g.tp.sum() / max(1, g.tp.sum() + g.fn.sum())
        rows.append((NICE.get(model, model), arm, len(g), g.machine_correct.corr(g.enum_correct), d.abs().mean(), d.mean(), 100 * (d.abs() <= 5).mean(), prec, rec, g.cost.mean() if g.cost.notna().any() else None))
    rows.sort(key=lambda r: (r[0] != 'Baseline: STT + alignment', r[4]))
    for n, arm, k, r_, mae, bias, w5, prec, rec, cost in rows:
        O.append(f"| {n} | {arm} | {k} | {r_:.2f} | {mae:.1f} | {bias:+.1f} | {w5:.0f}% | {'' if prec is None else f'{prec:.2f}'} | {'' if rec is None else f'{rec:.2f}'} | {'' if cost is None else f'{cost:.4f}'} |")
    O.append('')
# baseline per-word precision from reading_items
it = pd.read_csv('harness/reading_items.csv')
O += ['Baseline per-word precision / recall on all recordings (same rule, words both sides reached):', '']
for sub, d in it.groupby('sub'):
    tp = ((d.machine_wrong == 1) & (d.enum_wrong == 1)).sum(); fp = ((d.machine_wrong == 1) & (d.enum_wrong == 0)).sum(); fn = ((d.machine_wrong == 0) & (d.enum_wrong == 1)).sum()
    O.append(f"- {SUBN.get(sub, sub)}: precision {tp / max(1, tp + fp):.2f}, recall {tp / max(1, tp + fn):.2f} ({len(d):,} words)")
O.append('')

# ---- comprehension
if os.path.exists('harness/comprehension_scores.csv'):
    c = pd.read_csv('harness/comprehension_scores.csv')
    O += ['## 4. Comprehension answers (Urdu, six questions), graded from the transcript', '', f'Human floor for this subtask: {floor("rdcomp_urd")}. The grader sees the passage and the diarised question window.', '',
          '| Grader | n | r | MAE (questions) | bias | exact | within 1 | $/child |', '|---|---:|---:|---:|---:|---:|---:|---:|']
    rows = []
    for model, g in c.groupby('model'):
        d = g.machine - g.enum; rows.append((NICE.get(model, model), len(g), g.machine.corr(g.enum), d.abs().mean(), d.mean(), 100 * (d == 0).mean(), 100 * (d.abs() <= 1).mean(), g.cost.mean() if g.cost.notna().any() else None))
    for n, k, r_, mae, bias, ex, w1, cost in sorted(rows, key=lambda r: r[3]):
        O.append(f"| {n} | {k} | {r_:.2f} | {mae:.2f} | {bias:+.2f} | {ex:.0f}% | {w1:.0f}% | {'' if cost is None else f'{cost:.4f}'} |")
    O.append('')

# ---- segmenter
rows = []
for p in glob.glob('harness/segmenter_llm_*.csv'):
    d = pd.read_csv(p).dropna(subset=['within5']); model = os.path.basename(p)[len('segmenter_llm_'):-4].replace('_', '/', 1)
    if len(d): rows.append((NICE.get(model, model), len(d), int(d.n_common.sum()), 100 * d.within5.sum() / d.n_common.sum(), 100 * d.within15.sum() / d.n_common.sum(), d.mean_abs_start_err.mean(), d.cost.mean() if d.cost.notna().any() else None))
O += ['## 5. Finding the windows (segmenter labeller on STT timestamps)', '', 'The labeller reads the diarised, timestamped transcript and names first/last turn per subtask; the clock is Soniox\'s. Compared with the enumerator\'s tablet taps, which precede the child\'s first word by 5–15 s.', '',
      '| Labeller | files | subtasks matched | start within 5 s | within 15 s | mean abs error | $/file |', '|---|---:|---:|---:|---:|---:|---:|']
for n, f_, cm, w5, w15, err, cost in sorted(rows, key=lambda r: -r[4]):
    O.append(f"| {n} | {f_} | {cm} | {w5:.0f}% | {w15:.0f}% | {err:.1f} s | {'' if cost is None else f'{cost:.4f}'} |")
O += ['', 'Audio-native models were also tried as the clock: Gemini 2.5 Pro drifted 20–75 s and Gemini 2.5 Flash returned a transcript dump. The clock must come from speech-to-text; a text labeller then only has to name turns. In the product the coach\'s cue phrase replaces most of this.', '']

# ---- maths
rows = []
ENUM = ['wrdpblm', 'bleffcomp', 'numrep', 'idnummag', 'patterns']
for p in glob.glob('harness/maths_scores_*.csv'):
    d = pd.read_csv(p); model = os.path.basename(p)[len('maths_scores_'):-4].replace('_', '/', 1)
    for sub in ENUM:
        g = d.dropna(subset=[f'{sub}_machine', f'{sub}_enum']).copy()
        if len(g) < 5: continue
        g[f'{sub}_enum'] = pd.to_numeric(g[f'{sub}_enum']); diff = g[f'{sub}_machine'] - g[f'{sub}_enum']
        rows.append((sub, NICE.get(model, model), len(g), g[f'{sub}_machine'].corr(g[f'{sub}_enum']), diff.abs().mean(), diff.mean(), 100 * (diff == 0).mean(), 100 * (diff.abs() <= 1).mean(), d.cost.mean() if d.cost.notna().any() else None))
O += ['## 6. Maths from the spoken transcript', '', 'The grader sees the diarised maths-block transcript with no item bank (the study export has none). Items whose question is spoken are gradable; items whose stimulus is on paper are not from audio alone, and the product will have the bank.', '',
      '| Subtask | Grader | n | r | MAE (items) | bias | exact | within 1 | human floor | $/child |', '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for sub, n, k, r_, mae, bias, ex, w1, cost in sorted(rows, key=lambda r: (ENUM.index(r[0]), r[4])):
    O.append(f"| {sub} | {n} | {k} | {r_:.2f} | {mae:.2f} | {bias:+.2f} | {ex:.0f}% | {w1:.0f}% | {floor(sub)} | {'' if cost is None else f'{cost:.3f}'} |")
O.append('')

# ---- English pronunciation vendors
O += ['## 7. English pronunciation services', '',
      '- **SpeechAce** (scripted endpoint, first 29 s of each window, quality < 40 = wrong): count r 0.74 (word list) / 0.87 (story), MAE 8–11 words, per-word precision 0.21–0.25 on this 8 kHz audio. Median quality score 40–46 for words the enumerator accepted vs 30–34 for words she rejected: the separation exists but is weak.',
      '- **Azure Pronunciation Assessment**: not evaluated. Both documented keys return 401 from the Southeast Asia endpoint and the same key is on the production service, so English reading has been on the silent fallback path (P1 bug filed).', '']

# ---- what it adds up to
O += ['## 8. What it adds up to: the stack we recommend', '',
      '| Job | Use | Because | Fallback |', '|---|---|---|---|',
      '| Cutting the audio into subtask windows | The coach\'s cue phrase per block + speech-to-text timestamps (Soniox for Urdu, whisper-1 forced to English) | STT clocks were exact to the second; every audio LLM\'s clock drifted | A cheap text labeller (Gemini 3 Flash tier) on the diarised transcript when a coach forgets the cue |',
      '| Counting words correct in 60 s, Urdu and English | **Gemini 3.8 Flash on the clip with the printed text** (Gemini 3.1 Pro where a second opinion is worth 6× the cost) | Best MAE and rank agreement of everything tried, on par with or better than the alignment baseline while also giving per-word marks; ~1¢ per window | STT + alignment (the round-1 baseline) if the audio model is unavailable |',
      '| Per-word chips for the coach | Gemini 3.1 Pro / 3.8 Flash verdicts, shown only where the model and the alignment agree | Their precision is the best measured but still well under 1, so chips are suggestions, not marks | Coach marks the word |',
      '| Letters and initial sounds | Coach marks; keep the audio for a later open forced-alignment / GOP layer | Letter names transcribe in three scripts; the window is lost most of the time | — |',
      '| Comprehension answers | A text grader on the diarised question window (Gemini 3 Flash tier is enough) | Within one answer of the enumerator for ~75–80% of children at ~$0.001 | Claude Sonnet 5 / GPT-5 mini give the same result at higher cost |',
      '| Spoken maths | Transcript + the item bank + a number-word grammar; text grader only for word problems | Word problems r ≈ 0.7 without the bank; number ID needs the bank | Coach marks |',
      '| Written maths (photo) | Gemini 3.1 Pro vision with the answer key | Best on handwriting benchmarks; not yet tested on our sheets | Coach marks |',
      '| English phoneme detail | Azure Pronunciation Assessment once the key is regenerated; SpeechAce for nonwords | Only vendors with phoneme output; SpeechAce is weak on 8 kHz audio and should be re-measured on 16 kHz voice notes | — |',
      '| Coach protocol audit | Gemini-class audio model over the whole block, once, in the background | Caught a slip the human reviewer missed | — |', '',
      '**Models tried and set aside:** GPT audio mini and Nemotron omni (counts wrong by 15–30 words); MiMo 2.5, Voxtral small and Gemini 2.5 Flash (lenient, +8–10 words); every transcript-only LLM (no better than alignment, and harsher); GPT audio (good on word lists, poor on the Urdu story, 4× the cost of Gemini 3.8 Flash).', '']
open('harness/HARNESS_RESULTS.md', 'w').write('\n'.join(O))
print('\n'.join(O))
