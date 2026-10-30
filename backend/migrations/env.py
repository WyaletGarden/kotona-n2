from alembic import context
from sqlalchemy import create_engine, pool
from backend.config import settings
from backend.db import Base
from backend import models  # noqa: F401

target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(
        url=settings().database_url, target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:

    def run(connection):
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    supplied = context.config.attributes.get("connection")
    if supplied is not None:
        run(supplied)
    else:
        engine = create_engine(settings().database_url, poolclass=pool.NullPool)
        with engine.connect() as connection:
            run(connection)
