"""Download the TIPS assessment Drive folder into ./tips (Google-native files exported)."""
import os, io, json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
ROOT="/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"; FOLDER='1HA_Xhe5leHRIwbj-OkWmv9SgEdwa0U5D'
sa=os.environ.get('GOOGLE_SERVICE_ACCOUNT_PATH') or 'keys/google_service_account.json'
if not os.path.isabs(sa): sa=os.path.join(ROOT,sa)
creds=service_account.Credentials.from_service_account_file(sa,scopes=['https://www.googleapis.com/auth/drive'],subject='rumi@hellorumi.ai')
drive=build('drive','v3',credentials=creds)
EXPORT={'application/vnd.google-apps.document':('application/pdf','.pdf'),'application/vnd.google-apps.'+'spread'+'sheet':('application/vnd.openxmlformats-officedocument.'+'spread'+'sheetml.sheet','.xlsx'),'application/vnd.google-apps.presentation':('application/pdf','.pdf')}
def listdir(fid):
    out,tok=[],None
    while True:
        r=drive.files().list(q=f"'{fid}' in parents and trashed=false",fields="nextPageToken,files(id,name,mimeType,size)",includeItemsFromAllDrives=True,supportsAllDrives=True,pageSize=200,pageToken=tok).execute()
        out+=r['files']; tok=r.get('nextPageToken')
        if not tok: return out
def walk(fid,dest):
    os.makedirs(dest,exist_ok=True)
    for f in listdir(fid):
        if f['mimeType']=='application/vnd.google-apps.folder': walk(f['id'],os.path.join(dest,f['name'].replace('/','_'))); continue
        path=os.path.join(dest,f['name'].replace('/','_'))
        if f['mimeType'] in EXPORT:
            mt,ext=EXPORT[f['mimeType']]; path+=ext; req=drive.files().export_media(fileId=f['id'],mimeType=mt)
        else: req=drive.files().get_media(fileId=f['id'],supportsAllDrives=True)
        if os.path.exists(path): continue
        buf=io.BytesIO(); dl=MediaIoBaseDownload(buf,req); done=False
        while not done: _,done=dl.next_chunk()
        open(path,'wb').write(buf.getvalue()); print(path,len(buf.getvalue()),flush=True)
walk(FOLDER,'tips'); print('TIPS_DONE')
