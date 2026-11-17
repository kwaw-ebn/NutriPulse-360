import os,json,time,hashlib,secrets
from pathlib import Path
from datetime import datetime,timezone,date
from io import BytesIO
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI,Depends,HTTPException,Response,Request,Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from .db import Session,engine,Facility,User,Report,Action,Audit,Setting,LoginAttempt,ActionFollowup,ReviewRecord
from .security import db,current_user,admin,hash_password,verify_password,issue_token
from .indicators import INDICATORS,FIELDS,calculate,validate_counts
ROOT=Path(__file__).resolve().parents[2]
def now():return datetime.now(timezone.utc).isoformat()
def audit(s,u,event,oid=''):
 s.add(Audit(user_id=u.id if u else None,event=event,object_id=str(oid),created_at=now()))
def visible(s,u):
 q=select(Facility).where(Facility.active==True)
 if u.role=='facility':q=q.where(Facility.id==u.facility_id)
 if u.role=='subdistrict':q=q.where(Facility.subdistrict==u.subdistrict)
 return list(s.scalars(q.order_by(Facility.name)))
def access(s,u,fid):
 if fid not in [f.id for f in visible(s,u)]:raise HTTPException(403,'Facility is outside your reporting scope')
def settings(s):
 x=s.get(Setting,'config');return x.value if x else {'wellness_population':None,'wellness_facility_id':None,'population':108787,'baseline_year':2025,'growth_rate':None}
def results(s,facilities,year,month,module,extra=None):
 ids=[f.id for f in facilities];cfg=settings(s)
 reports=list(s.scalars(select(Report).where(Report.facility_id.in_(ids),Report.year==year,Report.month<=month,Report.module==module,Report.status=='approved')))
 if extra:reports=[r for r in reports if r.id!=extra.id]+[extra]
 out=[]
 for d in [x for x in INDICATORS if x['module']==module]:
  rr=[r for r in reports if (d['period']!='half' or (r.month-1)//6==(month-1)//6)]
  if d['code']=='3.31':rr=[r for r in rr if r.facility_id==cfg.get('wellness_facility_id')]
  n=sum(r.data.get(d['numerator'],0) for r in rr)
  if d['period']=='ratio':den=sum(r.data.get(d['denominator'],0) for r in rr)
  elif d['code']=='3.31':den=cfg.get('wellness_population') if cfg.get('wellness_facility_id') in ids else None
  else:den=sum(getattr(f,d['denominator']) for f in facilities) if rr else None
  out.append(calculate(d,n,den,month))
 return out

def serialize(r):return {k:getattr(r,k) for k in ['id','facility_id','year','month','module','status','data','updated_at','review_comment']}
def seed():
 with Session() as s:
  if not s.scalar(select(func.count(Facility.id))):
   for f in json.loads((ROOT/'data/facilities.json').read_text()):s.add(Facility(**f))
  if not s.get(Setting,'config'):s.add(Setting(key='config',value={'population':108787,'baseline_year':2025,'growth_rate':None,'wellness_population':None,'wellness_facility_id':None}))
  email=os.getenv('ADMIN_EMAIL');password=os.getenv('ADMIN_PASSWORD')
  if email and password and not s.scalar(select(User).where(User.email==email.lower())):
   if len(password)<12:raise RuntimeError('Administrator password must have at least 12 characters')
   s.add(User(email=email.lower(),name='Ebenezer Kwaw',password_hash=hash_password(password),role='district'))
  s.commit()
@asynccontextmanager
async def lifespan(app):
 seed();yield
app=FastAPI(title='NutriPulse 360 API',version='0.1.0',lifespan=lifespan)
origins=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','http://localhost:5173').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=['GET','POST','PUT'],allow_headers=['Content-Type','X-CSRF-Token'])
@app.middleware('http')
async def security_headers(request,call_next):
 response=await call_next(request)
 response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'strict-origin-when-cross-origin','Cache-Control':'no-store'})
 return response
@app.get('/health')
def health(s=Depends(db)):
 s.execute(select(1));return {'status':'ok','application':'NutriPulse 360'}
class Login(BaseModel):
 email:str=Field(max_length=200);password:str=Field(max_length=256)
@app.post('/api/auth/login')
def login(body:Login,response:Response,request:Request,s=Depends(db)):
 key=hashlib.sha256(body.email.strip().lower().encode()).hexdigest();a=s.get(LoginAttempt,key)
 if a and a.locked_until>time.time():raise HTTPException(429,'Too many attempts. Try again in 15 minutes.')
 u=s.scalar(select(User).where(User.email==body.email.strip().lower()))
 if not u or not u.active or not verify_password(body.password,u.password_hash):
  if not a:a=LoginAttempt(key=key,failures=0,locked_until=0);s.add(a)
  a.failures+=1
  if a.failures>=5:a.locked_until=time.time()+900;a.failures=0
  s.commit();raise HTTPException(401,'Email or password is incorrect')
 if a:s.delete(a)
 token,csrf=issue_token(u)
 response.set_cookie('np_session',token,httponly=True,secure=os.getenv('COOKIE_SECURE','true')=='true',samesite='none' if os.getenv('COOKIE_SECURE','true')=='true' else 'lax',max_age=28800)
 audit(s,u,'login');s.commit();return {'csrf':csrf,'user':user_info(u)}
def user_info(u):return {k:getattr(u,k) for k in ['id','name','email','role','facility_id','subdistrict']}
@app.get('/api/auth/me')
def me(request:Request,u=Depends(current_user)):
 import jwt
 from .security import SECRET
 return {'user':user_info(u),'csrf':jwt.decode(request.cookies['np_session'],SECRET,algorithms=['HS256'])['csrf']}
@app.post('/api/auth/logout')
def logout(response:Response,u=Depends(current_user)):
 response.delete_cookie('np_session',secure=os.getenv('COOKIE_SECURE','true')=='true',samesite='none' if os.getenv('COOKIE_SECURE','true')=='true' else 'lax');return {'ok':True}
class PasswordChange(BaseModel):
 current_password:str;new_password:str=Field(min_length=12,max_length=128)
@app.post('/api/auth/password')
def change_password(body:PasswordChange,u=Depends(current_user),s=Depends(db)):
 obj=s.get(User,u.id)
 if not verify_password(body.current_password,obj.password_hash):raise HTTPException(400,'Current password is incorrect')
 obj.password_hash=hash_password(body.new_password);audit(s,u,'password_changed');s.commit();return {'ok':True}
@app.get('/api/reference')
def reference(u=Depends(current_user),s=Depends(db)):
 facilities=visible(s,u)
 return {'facilities':[{k:getattr(f,k) for k in ['id','name','subdistrict','population','under5','vitamin_a_population']} for f in facilities],'indicators':INDICATORS,'fields':FIELDS,'config':settings(s),'warnings':[
 'Approved district baseline: 108,787 (2025). Facility populations sum to 108,768; Sheet1 district total is 108,767. No automatic redistribution has been applied.',
 'Imported age-group denominators are baseline source values. Several workbook cells are inconsistent; confirm them before operational reporting. Future growth projections are not approved.',
 'The nutrition template records initiation within 3 minutes; indicator 1.16 requires within 1 hour. The MVP collects both separately.',
 'Wellness form is a provisional aggregate MVP format. A dedicated Wellness Clinic reporting template was not supplied. Diabetes and hypertension ranges have unspecified units and are not scored.',
 'Unique annual and half-year counts must exclude people counted in earlier months. No patient identifiers are stored.' ]}
@app.get('/api/dashboard')
def dashboard(year:int=Query(default=2026,ge=2025,le=2100),month:int=Query(default=1,ge=1,le=12),subdistrict:str='',facility_id:int=0,u=Depends(current_user),s=Depends(db)):
 fs=visible(s,u)
 if subdistrict:fs=[f for f in fs if f.subdistrict==subdistrict]
 if facility_id:fs=[f for f in fs if f.id==facility_id]
 ids=[f.id for f in fs];rs=list(s.scalars(select(Report).where(Report.facility_id.in_(ids),Report.year==year,Report.month==month)))
 allr=list(s.scalars(select(Report).where(Report.facility_id.in_(ids))))
 aids=[r.id for r in allr];acts=list(s.scalars(select(Action).where(Action.report_id.in_(aids),Action.status!='completed')))
 cfg=settings(s);expected=len(fs)+(1 if cfg.get('wellness_facility_id') in ids else 0)
 submitted=sum(r.status in ['submitted','approved'] for r in rs)
 trend=[]
 for m in range(1,month+1):
  r=results(s,fs,year,m,'nutrition');trend.append({'month':m,'breastfeeding':r[0]['value'],'anaemia':r[2]['value'],'vitamin_a':r[3]['value']})
 return {'population':108787,'facilities':len(fs),'expected_reports':expected,'submitted_reports':submitted,'completeness':round(100*submitted/expected,1) if expected else 0,'pending':sum(r.status=='submitted' for r in rs),'open_actions':len(acts),'overdue_actions':sum(a.details.get('deadline','9999')<date.today().isoformat() for a in acts),'indicators':results(s,fs,year,month,'nutrition')+results(s,fs,year,month,'wellness'),'trend':trend,'comparisons':[{'name':f.name,'subdistrict':f.subdistrict,'indicators':results(s,[f],year,month,'nutrition')} for f in fs]}
class ReportInput(BaseModel):
 model_config=ConfigDict(extra='forbid')
 facility_id:int;year:int=Field(ge=2025,le=2100);month:int=Field(ge=1,le=12);module:Literal['nutrition','wellness'];data:dict[str,int]
 actions:dict[str,dict[str,str]]=Field(default_factory=dict)
 submit:bool=False
 attested:bool=False
ACTION_KEYS=['what_went_wrong','reasons','corrective_actions','next_month','responsible_officer','deadline','support_required']
@app.post('/api/reports')
def save_report(body:ReportInput,u=Depends(current_user),s=Depends(db)):
 access(s,u,body.facility_id)
 if (body.year,body.month)>(date.today().year,date.today().month):raise HTTPException(400,'Future reporting periods are not allowed')
 cfg=settings(s)
 if body.module=='wellness' and cfg.get('wellness_facility_id')!=body.facility_id:raise HTTPException(400,'District administrator must designate this facility as the Wellness Clinic first')
 try:validate_counts(body.module,body.data)
 except ValueError as e:raise HTTPException(422,str(e))
 if set(body.data)!={f[0] for f in FIELDS[body.module]}:raise HTTPException(422,'Complete every reporting field; use zero only for confirmed nil counts')
 r=s.scalar(select(Report).where(Report.facility_id==body.facility_id,Report.year==body.year,Report.month==body.month,Report.module==body.module))
 if r and r.status in ['approved','submitted']:raise HTTPException(409,'Report is locked for review. Ask the district officer to return it.')
 if not r:r=Report(facility_id=body.facility_id,year=body.year,month=body.month,module=body.module,created_by=u.id,status='draft');s.add(r)
 r.data=body.data;r.updated_at=now();s.flush()
 f=s.get(Facility,body.facility_id);calc=results(s,[f],body.year,body.month,body.module,r)
 # A nil denominator with positive numerator is invalid, and absent measures require an explanation before submission.
 if any(x['period'] in ['annual','half'] and x['denominator'] and x['numerator']>x['denominator'] for x in calc):
  s.rollback();raise HTTPException(422,'Cumulative unique attendees cannot exceed their eligible population. Check for duplicate counting.')
 required=[x['code'] for x in calc if x['status'] in ['below_target','no_data']]
 existing={a.indicator:a for a in s.scalars(select(Action).where(Action.report_id==r.id))}
 for code,details in body.actions.items():
  if code not in {x['code'] for x in calc}:raise HTTPException(422,'Unknown action indicator')
  if any(not details.get(k,'').strip() for k in ACTION_KEYS):raise HTTPException(422,'Complete all seven corrective action fields')
  try:date.fromisoformat(details['deadline'])
  except ValueError:raise HTTPException(422,'Invalid action deadline')
  a=existing.get(code)
  if not a:a=Action(report_id=r.id,indicator=code,status='open');s.add(a)
  a.details={k:details[k][:3000] for k in ACTION_KEYS};a.updated_at=now()
 if body.submit:
  if not body.attested:raise HTTPException(422,'Confirm that counts were checked and cumulative unique counts were deduplicated')
  missing=[c for c in required if c not in body.actions and (c not in existing or any(not existing[c].details.get(k,'').strip() for k in ACTION_KEYS))]
  if missing:
   s.rollback();raise HTTPException(422,{'message':'Corrective action is required before submission','required_indicators':missing,'results':calc})
  if body.module=='wellness' and not cfg.get('wellness_population'):s.rollback();raise HTTPException(422,'Approve the Wellness Clinic eligible population before submission')
  r.status='submitted'
 else:r.status='draft'
 audit(s,u,'report_'+r.status,r.id)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'A report for this facility and period already exists')
 return {'report':serialize(r),'results':calc}
@app.get('/api/reports')
def reports(year:int=2026,month:int=0,u=Depends(current_user),s=Depends(db)):
 q=select(Report).where(Report.facility_id.in_([f.id for f in visible(s,u)]),Report.year==year)
 if month:q=q.where(Report.month==month)
 return [serialize(r) for r in s.scalars(q.order_by(Report.month.desc(),Report.id.desc()))]
class Review(BaseModel):
 decision:Literal['approved','returned'];comment:str=Field(min_length=1,max_length=3000)
@app.post('/api/reports/{rid}/review')
def review(rid:int,body:Review,u=Depends(admin),s=Depends(db)):
 r=s.get(Report,rid)
 if not r:raise HTTPException(404,'Report not found')
 if body.decision=='approved' and r.status!='submitted':raise HTTPException(409,'Only submitted reports can be approved')
 if body.decision=='approved' and r.created_by==u.id:raise HTTPException(403,'A different district reviewer must approve your report')
 s.add(ReviewRecord(report_id=rid,user_id=u.id,decision=body.decision,comment=body.comment,created_at=now()))
 r.status=body.decision;r.review_comment=body.comment;r.updated_at=now();audit(s,u,'report_'+body.decision,rid);s.commit();return serialize(r)
@app.get('/api/actions')
def actions(u=Depends(current_user),s=Depends(db)):
 rs=list(s.scalars(select(Report).where(Report.facility_id.in_([f.id for f in visible(s,u)]))));rm={r.id:r for r in rs}
 return [{'id':a.id,'report_id':a.report_id,'indicator':a.indicator,'details':a.details,'status':a.status,'comment':a.comment,'history':[{'status':h.status,'comment':h.comment,'created_at':h.created_at,'user_id':h.user_id} for h in s.scalars(select(ActionFollowup).where(ActionFollowup.action_id==a.id).order_by(ActionFollowup.id))],'facility_id':rm[a.report_id].facility_id,'year':rm[a.report_id].year,'month':rm[a.report_id].month} for a in s.scalars(select(Action).where(Action.report_id.in_(list(rm))).order_by(Action.id.desc()))]
class Followup(BaseModel):
 status:Literal['open','in_progress','completed','returned'];comment:str=Field(min_length=1,max_length=3000)
@app.post('/api/actions/{aid}/followup')
def followup(aid:int,body:Followup,u=Depends(current_user),s=Depends(db)):
 a=s.get(Action,aid)
 if not a:raise HTTPException(404,'Action not found')
 access(s,u,s.get(Report,a.report_id).facility_id)
 if u.role!='district' and body.status in ['completed','returned']:raise HTTPException(403,'Only the district reviewer can close or return an action')
 s.add(ActionFollowup(action_id=aid,user_id=u.id,status=body.status,comment=body.comment,created_at=now()))
 a.status=body.status;a.comment=body.comment;a.updated_at=now();audit(s,u,'action_'+body.status,aid);s.commit();return {'ok':True}
class ConfigInput(BaseModel):
 wellness_population:float|None=Field(default=None,gt=0);wellness_facility_id:int|None=None
@app.put('/api/settings')
def update_settings(body:ConfigInput,u=Depends(admin),s=Depends(db)):
 if body.wellness_facility_id and not s.get(Facility,body.wellness_facility_id):raise HTTPException(422,'Unknown facility')
 if body.wellness_population and not body.wellness_facility_id:raise HTTPException(422,'Select the District Hospital Wellness Clinic')
 cfg=settings(s);cfg={**cfg,**body.model_dump()};s.get(Setting,'config').value=cfg;audit(s,u,'wellness_denominator_approved');s.commit();return cfg
class UserInput(BaseModel):
 name:str=Field(min_length=2,max_length=100);email:str=Field(min_length=5,max_length=200);password:str=Field(min_length=12,max_length=128);role:Literal['district','subdistrict','facility'];facility_id:int|None=None;subdistrict:str|None=None
@app.post('/api/users')
def create_user(body:UserInput,u=Depends(admin),s=Depends(db)):
 if '@' not in body.email:raise HTTPException(422,'A valid email is required')
 if body.role=='facility' and not s.get(Facility,body.facility_id):raise HTTPException(422,'Select a facility')
 if body.role=='subdistrict' and body.subdistrict not in set(s.scalars(select(Facility.subdistrict))):raise HTTPException(422,'Select a subdistrict')
 obj=User(name=body.name,email=body.email.lower(),password_hash=hash_password(body.password),role=body.role,facility_id=body.facility_id if body.role=='facility' else None,subdistrict=body.subdistrict if body.role=='subdistrict' else None)
 s.add(obj);audit(s,u,'user_created')
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'Email is already registered')
 return user_info(obj)
@app.get('/api/users')
def users(u=Depends(admin),s=Depends(db)):return [user_info(x) for x in s.scalars(select(User).order_by(User.name))]
@app.get('/api/audit')
def audit_list(u=Depends(admin),s=Depends(db)):
 return [{'id':a.id,'event':a.event,'object_id':a.object_id,'user_id':a.user_id,'created_at':a.created_at} for a in s.scalars(select(Audit).order_by(Audit.id.desc()).limit(200))]
@app.get('/api/export/{kind}')
def export(kind:Literal['xlsx','pdf'],year:int=2026,month:int=1,u=Depends(current_user),s=Depends(db)):
 if not 1<=month<=12:raise HTTPException(422,'Invalid month')
 fs=visible(s,u);rs=results(s,fs,year,month,'nutrition')+results(s,fs,year,month,'wellness');buf=BytesIO()
 rows=[['Code','Indicator','Numerator','Denominator','Actual %','Expected %','Status']]+[[r['code'],r['name'],r['numerator'],r['denominator'],r['value'],r['expected'],r['status']] for r in rs]
 if kind=='xlsx':
  from openpyxl import Workbook
  from openpyxl.styles import Font,PatternFill
  w=Workbook();sh=w.active;sh.title='Approved performance'
  for row in rows:sh.append(row)
  for c in sh[1]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='102C3A')
  for col,width in {'A':12,'B':42,'C':18,'D':18,'E':16,'F':16,'G':22}.items():sh.column_dimensions[col].width=width
  sh.freeze_panes='A2';notes=w.create_sheet('Notes');notes.append(['Year',year]);notes.append(['Month',month]);notes.append(['Scope',', '.join(f.name for f in fs)]);notes.append(['Basis','Approved reports only; population denominators: 2025 source baseline']);w.save(buf)
 else:
  from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer
  from reportlab.lib.styles import getSampleStyleSheet
  from reportlab.lib import colors
  from reportlab.lib.pagesizes import A4,landscape
  styles=getSampleStyleSheet();doc=SimpleDocTemplate(buf,pagesize=landscape(A4),rightMargin=25,leftMargin=25)
  tab=Table([[Paragraph(str(c if c is not None else 'Not configured'),styles['BodyText']) for c in row] for row in rows],colWidths=[42,220,70,90,65,70,110],repeatRows=1)
  tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dcefed')),('GRID',(0,0),(-1,-1),0.3,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP')]))
  doc.build([Paragraph('NutriPulse 360 | Agona East',styles['Title']),Paragraph(f'Approved performance • {year}-{month:02d} • 2025 baseline denominators',styles['Normal']),Spacer(1,15),tab,Spacer(1,15),Paragraph('Built by Ebenezer Kwaw | EK Synergy Ltd',styles['Normal'])])
 buf.seek(0);audit(s,u,'export_'+kind);s.commit()
 return StreamingResponse(buf,media_type='application/pdf' if kind=='pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="nutripulse-{year}-{month:02d}.{kind}"'})
