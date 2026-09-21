"""Download every file in the shared EGRA/EGMA enumerator-recordings Drive folder into ./audio.
Run: uv run --with google-api-python-client --with google-auth python download_drive_audio.py
Google-native files are exported (Sheets -> .xlsx, Docs -> .docx); binaries downloaded as-is.
"""
import os, io, json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

ROOT = "/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
FOLDER = '19tfSEeBaOchNwSB2VNZd9s9PmEpDAIkG'
G_SHEET = 'application/vnd.google-apps.' + 'spread' + 'sheet'
G_DOC = 'application/vnd.google-apps.document'
X_SHEET = 'application/vnd.openxmlformats-officedocument.' + 'spread' + 'sheetml.sheet'
X_DOC = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

sa = os.environ.get('GOOGLE_SERVICE_ACCOUNT_PATH') or 'keys/google_service_account.json'
if not os.path.isabs(sa):
    sa = os.path.join(ROOT, sa)
creds = service_account.Credentials.from_service_account_file(
    sa, scopes=['https://www.googleapis.com/auth/drive'], subject='rumi@hellorumi.ai')
drive = build('drive', 'v3', credentials=creds)


def listdir(fid):
    out, tok = [], None
    while True:
        r = drive.files().list(q=f"'{fid}' in parents and trashed=false",
                               fields="nextPageToken,files(id,name,mimeType,size,createdTime,modifiedTime)",
                               includeItemsFromAllDrives=True, supportsAllDrives=True,
                               pageSize=200, pageToken=tok).execute()
        out += r['files']
        tok = r.get('nextPageToken')
        if not tok:
            return out


files = listdir(FOLDER)
os.makedirs('audio', exist_ok=True)
json.dump(files, open('audio/_drive_manifest.json', 'w'), indent=1)
print(f"{len(files)} files in folder", flush=True)
for i, f in enumerate(files):
    if f['mimeType'] == 'application/vnd.google-apps.folder':
        print('SKIP folder', f['name'])
        continue
    name = f['name'].replace('Copy of ', '')
    path = os.path.join('audio', name)
    if f['mimeType'] == G_SHEET:
        path += '.xlsx'
        if os.path.exists(path):
            continue
        req = drive.files().export_media(fileId=f['id'], mimeType=X_SHEET)
    elif f['mimeType'] == G_DOC:
        path += '.docx'
        if os.path.exists(path):
            continue
        req = drive.files().export_media(fileId=f['id'], mimeType=X_DOC)
    else:
        if os.path.exists(path) and os.path.getsize(path) == int(f.get('size', 0)):
            continue
        req = drive.files().get_media(fileId=f['id'], supportsAllDrives=True)
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    open(path, 'wb').write(buf.getvalue())
    print(i + 1, name, len(buf.getvalue()), flush=True)
print('DONE', flush=True)
