import os,secrets,hashlib,hmac,time
import jwt
from fastapi import HTTPException,Request,Depends
from .db import Session,User
SECRET=os.getenv('JWT_SECRET')
if not SECRET:
 if os.getenv('RENDER'):raise RuntimeError('JWT_SECRET must be configured')
 SECRET=secrets.token_urlsafe(48)

def hash_password(password):
 salt=secrets.token_hex(16)
 return salt+':'+hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
def verify_password(password,stored):
 try:
  salt,digest=stored.split(':');return hmac.compare_digest(hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex(),digest)
 except (ValueError,TypeError):return False

def db():
 with Session() as s:yield s

def current_user(request:Request,s=Depends(db)):
 token=request.cookies.get('np_session')
 try:
  payload=jwt.decode(token,SECRET,algorithms=['HS256']);u=s.get(User,int(payload['sub']))
  if not u or not u.active or payload.get('ver')!=hashlib.sha256(u.password_hash.encode()).hexdigest()[:16]:raise ValueError()
 except Exception:raise HTTPException(401,'Please sign in')
 if request.method not in ('GET','HEAD','OPTIONS'):
  if not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),payload.get('csrf','')):raise HTTPException(403,'Invalid session protection token')
 return u

def issue_token(u):
 csrf=secrets.token_urlsafe(24)
 return jwt.encode({'sub':str(u.id),'csrf':csrf,'exp':int(time.time())+28800,'ver':hashlib.sha256(u.password_hash.encode()).hexdigest()[:16]},SECRET,algorithm='HS256'),csrf

def admin(u=Depends(current_user)):
 if u.role!='district':raise HTTPException(403,'District administrator access required')
 return u
