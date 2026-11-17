import os
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, ForeignKey, UniqueConstraint, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker

URL=os.getenv('DATABASE_URL','sqlite:///./nutripulse.db').replace('postgresql://','postgresql+psycopg://',1)
kwargs={'connect_args':{'check_same_thread':False}} if URL.startswith('sqlite') else {'pool_size':3,'max_overflow':2,'pool_timeout':15,'connect_args':{'connect_timeout':15}}
engine=create_engine(URL,pool_pre_ping=True,**kwargs)
Session=sessionmaker(bind=engine,expire_on_commit=False)
Base=declarative_base()
class Facility(Base):
 __tablename__='facilities'
 id=Column(Integer,primary_key=True);name=Column(String,nullable=False);subdistrict=Column(String,nullable=False);population=Column(Float,nullable=False);under5=Column(Float,nullable=False);vitamin_a_population=Column(Float,nullable=False);active=Column(Boolean,default=True)
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True);email=Column(String,unique=True,nullable=False);name=Column(String,nullable=False);password_hash=Column(String,nullable=False);role=Column(String,nullable=False);facility_id=Column(Integer,ForeignKey('facilities.id'));subdistrict=Column(String);active=Column(Boolean,default=True)
class Report(Base):
 __tablename__='reports';__table_args__=(UniqueConstraint('facility_id','year','month','module',name='uq_reporting_period'),)
 id=Column(Integer,primary_key=True);facility_id=Column(Integer,ForeignKey('facilities.id'),nullable=False,index=True);year=Column(Integer,nullable=False);month=Column(Integer,nullable=False);module=Column(String,nullable=False);status=Column(String,default='draft');data=Column(JSON,nullable=False);created_by=Column(Integer,ForeignKey('users.id'));updated_at=Column(String);review_comment=Column(Text,default='')
class Action(Base):
 __tablename__='actions'
 id=Column(Integer,primary_key=True);report_id=Column(Integer,ForeignKey('reports.id'),nullable=False,index=True);indicator=Column(String,nullable=False);details=Column(JSON,nullable=False);status=Column(String,default='open');comment=Column(Text,default='');updated_at=Column(String)
class Audit(Base):
 __tablename__='audit_logs'
 id=Column(Integer,primary_key=True);user_id=Column(Integer,ForeignKey('users.id'));event=Column(String,nullable=False);object_id=Column(String);created_at=Column(String,nullable=False)
class Setting(Base):
 __tablename__='settings'
 key=Column(String,primary_key=True);value=Column(JSON,nullable=False)
class LoginAttempt(Base):
 __tablename__='login_attempts'
 key=Column(String,primary_key=True);failures=Column(Integer,default=0);locked_until=Column(Float,default=0)

class ActionFollowup(Base):
 __tablename__='action_followups'
 id=Column(Integer,primary_key=True);action_id=Column(Integer,ForeignKey('actions.id'),nullable=False,index=True);user_id=Column(Integer,ForeignKey('users.id'),nullable=False);status=Column(String,nullable=False);comment=Column(Text,nullable=False);created_at=Column(String,nullable=False)
class ReviewRecord(Base):
 __tablename__='report_reviews'
 id=Column(Integer,primary_key=True);report_id=Column(Integer,ForeignKey('reports.id'),nullable=False,index=True);user_id=Column(Integer,ForeignKey('users.id'),nullable=False);decision=Column(String,nullable=False);comment=Column(Text,nullable=False);created_at=Column(String,nullable=False)
