"""Disposable-account authenticated HTTP checks. This is not device/UI UAT."""
import sys,json,time,uuid,secrets,base64,hmac,hashlib,struct,os
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[5];sys.path.insert(0,str(ROOT))
from shared.configuration import load_configuration
load_configuration()
from backend import db,settings
from supabase import create_client
import httpx
OUT=Path(__file__).parent;results=[];auth_id=None;app_id=None
BASE='http://127.0.0.1:8000';headers={}
def redact(v):
 if isinstance(v,dict):return {k:('[redacted]' if k in {'access_token','refresh_token','session_token','secret','token_hash','password'} else redact(x)) for k,x in v.items()}
 if isinstance(v,list):return [redact(x) for x in v]
 if isinstance(v,str) and ('http://' in v or 'https://' in v) and ('token=' in v or 'token%3D' in v):return v.split('?')[0]+'?[redacted]'
 return v
def persist():
 (OUT/'results.json').write_text(json.dumps(redact(results),indent=2,default=str))
def record(case,passed,detail):
 results.append({'case':case,'passed':bool(passed),'detail':redact(detail)})
 persist();print(case,'PASS' if passed else 'FAIL',flush=True)
def req(method,path,payload=None,expected=200,auth=True):
 t=time.monotonic();r=http.request(method,BASE+path,json=payload,headers=headers if auth else {})
 try:d=r.json()
 except ValueError:d={'bytes':len(r.content)}
 if r.status_code!=expected:raise RuntimeError(f'{method} {path}: HTTP {r.status_code}: '+str(redact(d))[:500])
 return d,round(time.monotonic()-t,3)
def snap_task(tid):
 s,_=req('GET','/mobile/me');return s,next(t for t in s['tasks'] if t['id']==tid)
client=None
try:
 with httpx.Client(timeout=125,trust_env=False) as http:
  d,_=req('GET','/mobile/me',expected=401,auth=False);record('AUTH-no-token',True,{'http':401})
  suffix=uuid.uuid4().hex[:12];email='roadie-check-'+suffix+'@example.com';password=secrets.token_urlsafe(28)+'aA1!'
  created=db.client().auth.admin.create_user({'email':email,'password':password,'email_confirm':True,'user_metadata':{'display_name':'Roadie disposable API test'}})
  auth_id=created.user.id
  client=create_client(settings.SUPABASE_URL,os.environ['SUPABASE_PUBLISHABLE_KEY'])
  session=client.auth.sign_in_with_password({'email':email,'password':password}).session
  headers={'Authorization':'Bearer '+session.access_token}
  me,_=req('GET','/accounts/me');app_id=me['user']['id'];record('AUTH-MFA-required',me['mfa_required'] and not me['access_allowed'],{'access_allowed':me['access_allowed']})
  req('GET','/mobile/me',expected=403);record('AUTH-AAL1-blocked',True,{'http':403})
  factor=client.auth.mfa.enroll({'factor_type':'totp','friendly_name':'Disposable automated test'})
  secret=base64.b32decode(factor.totp.secret.upper()+'='*((8-len(factor.totp.secret)%8)%8))
  counter=int(time.time())//30;digest=hmac.new(secret,struct.pack('>Q',counter),hashlib.sha1).digest();off=digest[-1]&15
  otp=str((struct.unpack('>I',digest[off:off+4])[0]&0x7fffffff)%1000000).zfill(6)
  client.auth.mfa.challenge_and_verify({'factor_id':factor.id,'code':otp})
  headers={'Authorization':'Bearer '+client.auth.get_session().access_token}
  me,_=req('GET','/accounts/me');record('AUTH-AAL2-access',me['access_allowed'] and me['user']['role']=='user',{'access_allowed':me['access_allowed'],'role':me['user']['role']})
  assert me['access_allowed']
  choices=[v for v in db.all_rows('knowledge_vehicles') if 'alza' in (v.get('name','')+' '+v.get('code','')).lower() and v.get('published')]
  assert choices,'Published Alza vehicle unavailable'
  catalogue_id=choices[0]['id'];vid=str(uuid.uuid4());tid=str(uuid.uuid4());rid=str(uuid.uuid4())
  vehicle={'catalogueId':catalogue_id,'name':'API Test Alza','plateNumber':'TEST-ONLY','mileage':21000}
  req('PUT','/mobile/me/vehicles/'+vid,vehicle)
  task={'id':tid,'vehicleId':vid,'title':'Manual test oil service','category':'Engine','action':'service','scheduleSource':'custom','customRule':{'type':'recurring','distanceKm':5000,'months':6},'isCustom':True}
  req('PUT','/mobile/me/tasks/'+tid,task)
  s,t=snap_task(tid);record('CAR-custom-baseline-missing',t['status']['label']=='Information required',{'status':t['status'],'scheduleSource':t['scheduleSource']})
  service={'id':rid,'vehicleId':vid,'taskId':tid,'title':'Manual test oil service','category':'Engine','mileage':20000,'date':'2026-10-06T12:00:00+08:00','notes':'Disposable API test baseline','performedBy':'mechanic','cost':120.50}
  req('PUT','/mobile/me/records/'+rid,service)
  s,t=snap_task(tid);st=t['status'];record('CAR-next-service',st.get('nextKm')==25000 and st.get('remainingKm')==4000 and str(st.get('nextDate'))=='2027-04-06',{'status':st,'record_count':len(s['records'])})
  for mileage,label in [(24000,'Due soon'),(25000,'Due / Overdue')]:
   vehicle['mileage']=mileage;req('PUT','/mobile/me/vehicles/'+vid,vehicle)
   s,t=snap_task(tid);record('CAR-mileage-'+str(mileage),t['status']['label']==label,{'status':t['status']})
  guides,_=req('GET','/guides?offset=0&limit=100');record('LEARN-published-content',bool(guides),{'available_guides':len(guides)})
  emergency,_=req('GET','/emergency/playbooks?offset=0&limit=100');contacts,_=req('GET','/emergency/contacts?offset=0&limit=100')
  record('SOS-published-protocols',bool(emergency) and all(p.get('steps') for p in emergency),{'protocol_count':len(emergency),'contact_count':len(contacts)})
  chat=None
  questions=[('AI-01-concept','I know nothing about cars. What does engine oil do, and why does it need changing? Explain any technical words.'),
             ('AI-02-follow-up','Can you explain that more simply, with an everyday example?'),
             ('AI-03-procedure','Using this car\'s manual, explain how to check the engine oil level, including preparation and precautions.'),
             ('AI-04-emergency','I have broken down and I am still exposed to moving traffic. Can you walk me through fixing the car here?'),
             ('AI-05-unsupported','What is the exact tightening torque for an aftermarket XYZ-brand turbo kit on my Alza? If your references do not cover it, say so.'),
             ('AI-personal-profile','What is the name of my saved car and its current recorded mileage?')]
  for name,question in questions:
   payload={'message':question}
   if name=='AI-02-follow-up' and chat:payload.update(session_id=chat['session_id'],session_token=chat['session_token'])
   d,seconds=req('POST','/chat',payload);chat=d;text=d['answer'].lower()
   if name=='AI-03-procedure':passed='warm up' in text and 'few minutes' in text and 'f' in text and 'l' in text
   elif name=='AI-04-emergency':passed=d.get('route')=='emergency'
   elif name=='AI-05-unsupported':passed=('specification' in text or 'cannot' in text or "don't have" in text) and 'n.m' not in text
   elif name=='AI-personal-profile':passed='api test alza' in text and '25,000' in text and '[P1]' in d['answer']
   else:passed=bool(d['answer'].strip()) and d.get('response_type') not in ['generation_error','retrieval_error']
   record(name,passed,{'seconds':seconds,'reply':d,'quality_review':'Transport/selected checks only; conceptual correctness and phone presentation require review.'})
   if name=='AI-03-procedure':
    (OUT/'procedure-reply.json').write_text(json.dumps(redact(d),indent=2))
  resumed,_=req('POST','/chat/sessions/'+chat['session_id']+'/resume');record('CHAT-persisted-session',bool(resumed),{'returned_keys':list(resumed) if isinstance(resumed,dict) else 'list'})
  iid=str(uuid.uuid4());now=datetime.now(timezone.utc).isoformat()
  incident={'id':iid,'type':'Stationary test — no real incident','occurredAt':now,'location':'Fictitious test location','details':'Disposable API check only','updatedAt':now,'photoCount':0}
  saved,_=req('PUT','/mobile/me/incidents/'+iid,incident)
  incidents,_=req('GET','/mobile/me/incidents');record('SOS-incident-persisted',any(i['id']==iid and not i['pendingSync'] for i in incidents),{'cloudRevision':saved['cloudRevision'],'photoCount':saved['photoCount']})
  changed={**incident,'details':'Updated fictitious test detail','cloudRevision':saved['cloudRevision']}
  req('PUT','/mobile/me/incidents/'+iid,changed)
  req('PUT','/mobile/me/incidents/'+iid,{**incident,'details':'Stale write attempt','cloudRevision':saved['cloudRevision']},expected=409)
  record('SOS-stale-incident-protected',True,{'http':409})
except BaseException as e:
 record('EXECUTION-ERROR',False,{'type':type(e).__name__,'message':str(e)[:650]})
finally:
 cleanup=[]
 if auth_id:
  try:
   for row in db.all_rows('app_users',auth_user_id=auth_id):
    db.delete('app_users',row['id'])
   db.client().auth.admin.delete_user(auth_id)
   cleanup.append('Disposable app profile/data and Auth user deleted.')
  except Exception as e:cleanup.append('Cleanup requires attention: '+type(e).__name__)
 (OUT/'summary.json').write_text(json.dumps({'scope':'Authenticated backend/API integration; no phone/emulator UI control available','model':'roadie-gemma3-ft','passed':sum(r['passed'] for r in results),'failed':sum(not r['passed'] for r in results),'cleanup':cleanup,'phone_ui_tests':'Blocked: no controllable connected phone/emulator; no UI, permission, offline, photos or external-app handoff pass claimed.'},indent=2))
 print('SUMMARY',json.loads((OUT/'summary.json').read_text()),flush=True)
