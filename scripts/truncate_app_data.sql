-- Все users / notes / tasks; счётчики id сбрасываются. Таблица alembic_version не меняется.
-- Пример: psql -h localhost -p 55432 -U postgres -d smart_notes -f scripts/truncate_app_data.sql

TRUNCATE tasks, notes, users RESTART IDENTITY CASCADE;
