import os
from alembic import context
from sqlalchemy import create_engine
from app.db import Base
config=context.config
target_metadata=Base.metadata
url=os.getenv('DATABASE_URL_UNPOOLED',os.getenv('DATABASE_URL','sqlite:///./nutripulse.db')).replace('postgresql://','postgresql+psycopg://',1)
if context.is_offline_mode():
 context.configure(url=url,target_metadata=target_metadata,literal_binds=True)
 with context.begin_transaction():context.run_migrations()
else:
 with create_engine(url).connect() as connection:
  context.configure(connection=connection,target_metadata=target_metadata)
  with context.begin_transaction():context.run_migrations()
