"""Harness step 2: extract per-child ground truth from the SurveyCTO export for the 206 matched recordings.
Writes harness/gt/<audio_filename>.json with: form timestamps per subtask, subtask scores, per-item flags
(1 = marked incorrect by the enumerator), maths item answers, and the coach QA verdicts.
Run: uv run --with openpyxl --with pandas python harness/02_ground_truth.py
"""
import openpyxl, pandas as pd, json, re, os

os.makedirs('harness/gt', exist_ok=True)
wb = openpyxl.load_workbook('audio/EGRA_EGMA client N=2233.xlsx', read_only=True)
ws = wb.worksheets[0]
it = ws.iter_rows(values_only=True)
hdr = [str(h) for h in next(it)]
rows = {}
uidx = hdr.index('unique_id_calc')
for r in it:
    rows[str(r[uidx])] = dict(zip(hdr, r))
idx = pd.read_csv('audio/_audio_index.csv')
qa = pd.read_csv('audio/_coach_reviews.csv')


def ts(v):
    if v is None or v == '':
        return None
    try:
        return pd.to_datetime(v).isoformat()
    except Exception:
        return None


def items(d, prefix, n):
    out = []
    for i in range(1, n + 1):
        v = d.get(f'{prefix}_{i}')
        out.append(None if v in (None, '') else int(float(v)))
    return out


SUB = [('listcomp_urd', 'start_listcomp_urd', 'end_listcomp_urd'), ('letterid_urd', 'start_letterid_urd', 'end_letterid_urd'),
       ('idwrd_urd', 'start_idwordrd_urd', 'end_idwordrd_urd'), ('orf_urd', 'start_orf_urd', 'start_rdcomp_urd'),
       ('rdcomp_urd', 'start_rdcomp_urd', 'end_rdcomp_urd'), ('listcomp_eng', 'start_listcomp_eng', 'end_listcomp_eng'),
       ('letterid_eng', 'start_letterid_eng', 'end_letterid_eng'), ('pw_eng', 'start_psuedowrdrd_eng', 'end_psuedowrdrd_eng'),
       ('idwrd_eng', 'start_idwordrd_eng', 'end_idwordrd_eng'), ('orf_eng', 'start_orf_eng', 'start_rdcomp_eng'),
       ('rdcomp_eng', 'start_rdcomp_eng', 'end_rdcomp_eng'), ('idnummag', 'start_idnummag', 'end_idnummag'),
       ('numrep', 'start_numrep', 'end_numrep'), ('blfluency', 'start_blfluency', 'start_bleffcomp'),
       ('bleffcomp', 'start_bleffcomp', 'end_bleffcomp'), ('wrdpblm', 'start_wrdpblm', 'end_wrdpblm'),
       ('patterns', 'start_patterns', 'end_patterns')]
SCORE_RE = re.compile(r'(numcorrect|percorrect|_60s_|score|attempted|correct|incorrect|time_remain|time_taken|firstline|no_orf|continue|milestone)')
n = 0
for _, a in idx.iterrows():
    uid = str(a.unique_id_calc)
    if uid not in rows:
        continue
    d = rows[uid]
    g = {
        'audio_filename': a.audio_filename, 'unique_id_calc': uid, 'enumerator': d.get('enumerator'),
        'grade': d.get('class_grade_a'), 'age': d.get('child_age'), 'home_lang': d.get('home_lang'),
        'form_start': ts(d.get('c_starttime') or d.get('starttime')), 'form_end': ts(d.get('c_endtime') or d.get('endtime')),
        'form_duration': str(d.get('duration')),
        'subtask_times': {k: {'start': ts(d.get(s)), 'end': ts(d.get(e))} for k, s, e in SUB},
        'scores': {k: d.get(k) for k in hdr if SCORE_RE.search(k) and not re.match(r'^(sec\d|blfl\d)', k) and d.get(k) not in (None, '')},
        'items': {
            'letterid_urd': items(d, 'letterid_fl_urd', 100), 'letterid_eng': items(d, 'letterid_fl_eng', 100),
            'idwrd_urd': items(d, 'idwrd_reading_urd', 50), 'idwrd_eng': items(d, 'idwrd_reading_eng', 50),
            'pw_eng': items(d, 'pw_reading_eng', 50), 'orf_urd': items(d, 'orf_reading_urd', 70), 'orf_eng': items(d, 'orf_reading_eng', 70),
            'listcomp_urd': [d.get(f'listcomp_lit{i}_urd') for i in range(1, 5)] + [d.get(f'listcomp_inf{i}_urd') for i in (1, 2)],
            'rdcomp_urd': [d.get(f'rdcomp_lit{i}_urd') for i in range(1, 5)] + [d.get(f'rdcomp_inf{i}_urd') for i in (1, 2)],
            'listcomp_eng': [d.get(f'listcomp_lit{i}_eng') for i in range(1, 5)] + [d.get(f'listcomp_inf{i}_eng') for i in (1, 2)],
            'rdcomp_eng': [d.get(f'rdcomp_lit{i}_eng') for i in range(1, 5)] + [d.get(f'rdcomp_inf{i}_eng') for i in (1, 2)],
            'identify': {k: d.get(k) for k in hdr if k.startswith('identify_')},
            'represent': {k: d.get(k) for k in hdr if k.startswith('represent_')},
            'computation': {k: d.get(k) for k in hdr if k.startswith('computation_')},
            'word_problems': {k: d.get(k) for k in hdr if k.startswith('word_problems_')},
            'patterns': {k: d.get(k) for k in hdr if k.startswith('patterns_')},
            'blfl': {k: d.get(k) for k in hdr if re.match(r'^blfl[l]?\d', k) and d.get(k) not in (None, '')},
        },
        'qa': [{'reviewer': x.reviewer, 'compliance': x.overall_compliance_pct, 'flagged': x.flagged, 'verdicts': x.verdicts_json,
                'comments': x.comments_json, 'overall_comment': x.overall_comment} for _, x in qa[qa.unique_id_calc == uid].iterrows()],
    }
    json.dump(g, open(f'harness/gt/{a.audio_filename}.json', 'w'), ensure_ascii=False, default=str)
    n += 1
print('wrote', n, 'ground-truth files')
ex = json.load(open(f'harness/gt/{idx.audio_filename.iloc[0]}.json'))
print('identify:', ex['items']['identify'])
print('computation:', ex['items']['computation'])
print('word_problems:', ex['items']['word_problems'])
print('blfl sample:', list(ex['items']['blfl'].items())[:30])
print('scores sample:', {k: v for k, v in list(ex['scores'].items())[:40]})
