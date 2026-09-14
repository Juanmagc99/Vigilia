# ADR 0001: Async SQLAlchemy persistence

Vigilia uses SQLAlchemy 2 with `AsyncSession` and psycopg. Sessions and transactions are created per operation and are never shared by concurrent work. Alembic remains the only schema migration mechanism.

SQLModel was removed so persistence models do not also act as API schemas. Pydantic contracts remain at the application and adapter boundaries.
