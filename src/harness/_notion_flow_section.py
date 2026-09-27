"""One-off: swap the 'The checking screen' section on PROJ-068 for the accurate WhatsApp Flow design.

Deletes every block between the 'The checking screen' heading_2 and the next heading_2, then inserts
the new text + three uploaded PNGs right after the heading (children PATCH with `after`).
"""
import os, re, time, requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
env = {}
for line in open(os.path.join(ROOT, '.env')):
    if '=' in line and not line.startswith('#'):
        k, v = line.rstrip('\n').split('=', 1); env[k.strip()] = v.strip().strip('"').strip("'")
TOK = os.environ.get('NOTION_TOKEN') or env.get('NOTION_TOKEN')
if not TOK:
    cred = open(os.path.join(ROOT, '01_Digital Coach Docs', '03_ACCESS_CREDENTIALS.md')).read()
    TOK = re.search(r'Integration Token: `(ntn_[A-Za-z0-9]+)`', cred).group(1)
H = {'Authorization': f'Bearer {TOK}', 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}
CARD = '3ddd4a97-15e9-8109-b6ae-f54db42e9de9'
MOCK = os.path.join(os.path.dirname(__file__), 'mockups')
SITE = 'https://hyasin270.github.io/egra-five-minutes/'

def rt(text, bold=False, italic=False, link=None):
    o = {'type': 'text', 'text': {'content': text}, 'annotations': {'bold': bold, 'italic': italic}}
    if link: o['text']['link'] = {'url': link}
    return o

def para(*runs): return {'object': 'block', 'type': 'paragraph', 'paragraph': {'rich_text': list(runs), 'color': 'default'}}
def bullet(*runs): return {'object': 'block', 'type': 'bulleted_list_item', 'bulleted_list_item': {'rich_text': list(runs), 'color': 'default'}}

def children(bid):
    out, cur = [], None
    while True:
        r = requests.get(f'https://api.notion.com/v1/blocks/{bid}/children', headers=H, params={'page_size': 100, **({'start_cursor': cur} if cur else {})}).json()
        out += r.get('results', [])
        if not r.get('has_more'): return out
        cur = r['next_cursor']

def plain(b):
    t = b.get(b['type'], {}).get('rich_text', [])
    return ''.join(x.get('plain_text', '') for x in t)

def upload(path):
    name = os.path.basename(path)
    r = requests.post('https://api.notion.com/v1/file_uploads', headers=H, json={'filename': name, 'content_type': 'image/png'}).json()
    fid = r['id']
    with open(path, 'rb') as f:
        r2 = requests.post(f'https://api.notion.com/v1/file_uploads/{fid}/send', headers={'Authorization': H['Authorization'], 'Notion-Version': H['Notion-Version']}, files={'file': (name, f, 'image/png')})
    assert r2.status_code == 200, r2.text
    return fid

def image(fid, caption):
    return {'object': 'block', 'type': 'image', 'image': {'type': 'file_upload', 'file_upload': {'id': fid}, 'caption': [rt(caption, italic=True)]}}

blocks = children(CARD)
idx = next(i for i, b in enumerate(blocks) if b['type'] == 'heading_2' and 'checking screen' in plain(b).lower())
head = blocks[idx]
j = idx + 1
old = []
while j < len(blocks) and blocks[j]['type'] not in ('heading_2', 'heading_1'):
    old.append(blocks[j]); j += 1
print('heading', head['id'], 'old blocks', len(old), [b['type'] for b in old])
for b in old:
    requests.delete(f"https://api.notion.com/v1/blocks/{b['id']}", headers=H); time.sleep(0.25)

ids = {n: upload(os.path.join(MOCK, n)) for n in ('chat_cta.png', 'flow_urdu.png', 'flow_maths.png')}
new = [
  para(rt('This is the same mechanism the lesson-observation form uses in Islamabad today. After a coach sends a lesson recording, Rumi listens, fills in the observation form and sends a message with a button that says '), rt('فارم کھولیں', bold=True), rt(' ("open the form"). Tapping it opens a WhatsApp Flow: a set of screens WhatsApp itself draws, where every score is already filled in; the coach changes what they disagree with, taps Next through the screens, and submits. We reuse that exactly, with one form per child instead of per lesson.')),
  para(rt('A WhatsApp Flow is not a web page, so the design has to fit what Meta allows. What it can do: fields pre-filled from our server; number boxes; a row of tappable chips (at most 20); radio buttons; dropdowns; a photo picker that opens the camera; one button per screen; up to 50 elements per screen. What it cannot do: '), rt('play audio', bold=True), rt('. There is no sound inside a Flow at all. So the coach does not re-listen inside the form; the recording is their own voice note, already in the chat, and they play it there. Each screen\'s button sends its values to Rumi as soon as it is tapped, so closing the form to listen and opening it again loses nothing.')),
  para(rt('That rules out the per-word tap-to-mark passage an app could offer (a 60-word story would need 60 elements and there is no tap-on-text component). What fits: the counts as pre-filled numbers; the words the computer marked wrong as chips that start ticked (the coach unticks any the child actually read right); one radio-button question per comprehension item showing the question and what the child said; a dropdown for the things the computer does not mark, such as first sounds and letters. Where the computer is not confident enough, the field arrives empty rather than pre-filled.')),
  image(ids['chat_cta.png'], '1 · The chat. Rumi sends the card, the coach records one voice note for the whole five minutes, Rumi replies within two minutes with its counts and the open-the-form button. The same message shape the observation form uses today.'),
  image(ids['flow_urdu.png'], '2 · Screen 1 of 3, Urdu. Pre-filled number boxes; the three words the computer heard wrong as ticked chips (untick = counts as right); each story question with the child\'s answer and three radio buttons; the green button saves the screen and moves to English.'),
  image(ids['flow_maths.png'], '3 · Screen 3 of 3, maths. Dropdowns for number reading and word problems, a number box for the timed sums, and the photo picker that opens the camera for the child\'s written answers. Submit ends the child and Rumi sends the next card.'),
  para(rt('The full draft of the form in the exact JSON format Meta accepts is on the project page: '), rt('egra-review-flow.json', link=SITE + 'harness/flow/egra-review-flow.json'), rt('. It uses only components that exist in Flow version 7.0 and every label is within Meta\'s length limits. The pictures above are rendered from that file\'s example data, not drawn separately.')),
  para(rt('Storage is unchanged from the observation form: the computer\'s answer is saved once and never changed (version 1); the form opens pre-filled from it; the coach\'s submission is saved as version 2 with a note of what changed, item by item, because we need to know exactly where the computer was wrong to improve it. Only the coach who did the assessment can submit it.')),
]
r = requests.patch(f'https://api.notion.com/v1/blocks/{CARD}/children', headers=H, json={'children': new, 'after': head['id']})
print(r.status_code, r.text[:200] if r.status_code != 200 else 'inserted', len(new))
