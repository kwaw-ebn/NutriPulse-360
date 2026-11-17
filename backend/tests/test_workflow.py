import os
os.environ['DATABASE_URL']='sqlite:///./test.db'
os.environ['COOKIE_SECURE']='false'
os.environ['JWT_SECRET']='test-secret-long-enough-for-local-workflow-verification'
from fastapi.testclient import TestClient
from app.db import Base,engine,Session,User,Facility,Report,Action
from app.main import app,seed
from app.security import hash_password
from app.indicators import INDICATORS,FIELDS,calculate
import pytest
@pytest.fixture(autouse=True)
def database():
 Base.metadata.drop_all(engine);Base.metadata.create_all(engine);seed()
 with Session() as s:
  for email,role,fid in [('admin@test.org','district',None),('reviewer@test.org','district',None),('facility@test.org','facility',1),('other@test.org','facility',2)]:
   s.add(User(name=email,email=email,password_hash=hash_password('TestingStrong123!'),role=role,facility_id=fid))
  s.commit()
 yield
 Base.metadata.drop_all(engine)
def client(email):
 c=TestClient(app);r=c.post('/api/auth/login',json={'email':email,'password':'TestingStrong123!'});assert r.status_code==200,r.text;c.headers['X-CSRF-Token']=r.json()['csrf'];return c

def body():
 d={k:0 for k,_,_ in FIELDS['nutrition']};d.update(deliveries=100,breastfed_1hr=98,weighed=100,underweight=2,hb_checked_36=100,anaemic_36=20,measured_unique=200,vitamin_a_unique=300)
 return {'facility_id':1,'year':2026,'month':1,'module':'nutrition','data':d,'submit':True,'attested':True}
def test_direction_and_milestones():
 assert calculate(INDICATORS[2],36,100,1)['status']=='below_target'
 assert calculate(INDICATORS[2],35,100,1)['status']=='achieved'
 assert calculate(INDICATORS[1],10,1000,6)['expected']==5
 assert calculate(INDICATORS[3],1,100,7)['expected']==13.33
 assert calculate(INDICATORS[3],0,None,12)['value'] is None

def test_auth_scope_csrf_and_roles():
 c=TestClient(app);assert c.get('/api/reference').status_code==401
 c=client('facility@test.org');assert len(c.get('/api/reference').json()['facilities'])==1
 assert c.get('/api/users').status_code==403
 b=body();b['facility_id']=2;assert c.post('/api/reports',json=b).status_code==403
 del c.headers['X-CSRF-Token'];assert c.post('/api/reports',json=body()).status_code==403

def test_corrective_actions_and_approval_and_exports():
 c=client('facility@test.org');b=body();b['data']['breastfed_1hr']=80
 r=c.post('/api/reports',json=b);assert r.status_code==422,r.text
 assert r.json()['detail']['required_indicators']==['1.16']
 b['actions']={'1.16':{'what_went_wrong':'Delayed support','reasons':'Staff shortage','corrective_actions':'Train staff','next_month':'Assign delivery lead','responsible_officer':'Officer A','deadline':'2026-12-30','support_required':'Training'}}
 r=c.post('/api/reports',json=b);assert r.status_code==200,r.text;rid=r.json()['report']['id']
 assert c.post('/api/reports',json=b).status_code==409
 admin=client('admin@test.org');before=admin.get('/api/dashboard?year=2026&month=1').json();assert before['indicators'][0]['value'] is None
 assert admin.post(f'/api/reports/{rid}/review',json={'decision':'approved','comment':'Registers checked'}).status_code==200
 after=admin.get('/api/dashboard?year=2026&month=1').json();assert after['indicators'][0]['value']==80
 assert admin.get('/api/export/xlsx?year=2026&month=1').content[:2]==b'PK'
 assert admin.get('/api/export/pdf?year=2026&month=1').content[:4]==b'%PDF'
 aid=c.get('/api/actions').json()[0]['id'];assert c.post(f'/api/actions/{aid}/followup',json={'status':'completed','comment':'Done'}).status_code==403
 assert admin.post(f'/api/actions/{aid}/followup',json={'status':'completed','comment':'Verified completion'}).status_code==200

def test_validation_and_self_approval():
 c=client('admin@test.org');b=body();b['data']['underweight']=101
 assert c.post('/api/reports',json=b).status_code==422
 b=body();r=c.post('/api/reports',json=b);assert r.status_code==200,r.text
 assert c.post(f"/api/reports/{r.json()['report']['id']}/review",json={'decision':'approved','comment':'Reviewed'}).status_code==403

def test_population_weighted_rates_and_wellness():
 c=client('admin@test.org');cfg=c.get('/api/reference').json()['config'];assert cfg['population']==108787;assert cfg['wellness_population'] is None
 assert c.put('/api/settings',json={'wellness_facility_id':1,'wellness_population':1000}).status_code==200
 with Session() as s:
  s.add_all([Report(facility_id=1,year=2026,month=1,module='nutrition',status='approved',data={'deliveries':10,'breastfed_1hr':10}),Report(facility_id=2,year=2026,month=1,module='nutrition',status='approved',data={'deliveries':90,'breastfed_1hr':0})]);s.commit()
 d=c.get('/api/dashboard?year=2026&month=1').json();assert d['indicators'][0]['value']==10

def test_password_change_revokes_session():
 c=client('facility@test.org');r=c.post('/api/auth/password',json={'current_password':'TestingStrong123!','new_password':'AChangedPassword123!'});assert r.status_code==200
 assert c.get('/api/reference').status_code==401
