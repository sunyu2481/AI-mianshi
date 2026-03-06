from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, inspect
from .config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # 数据库迁移：为已有表添加缺失的列
        def _get_columns(connection, table_name):
            insp = inspect(connection)
            if table_name not in insp.get_table_names():
                return None
            return [col['name'] for col in insp.get_columns(table_name)]

        columns = await conn.run_sync(lambda c: _get_columns(c, 'speech_configs'))
        if columns is not None and 'whisper_model' not in columns:
            await conn.execute(text(
                "ALTER TABLE speech_configs ADD COLUMN whisper_model VARCHAR(100) DEFAULT 'whisper-1'"
            ))

        # 为 model_configs 表添加 LLM 参数列
        mc_columns = await conn.run_sync(lambda c: _get_columns(c, 'model_configs'))
        if mc_columns is not None:
            if 'max_output_tokens' not in mc_columns:
                await conn.execute(text(
                    "ALTER TABLE model_configs ADD COLUMN max_output_tokens INTEGER DEFAULT 8192"
                ))
            if 'temperature' not in mc_columns:
                await conn.execute(text(
                    "ALTER TABLE model_configs ADD COLUMN temperature FLOAT DEFAULT 0.7"
                ))
            if 'top_p' not in mc_columns:
                await conn.execute(text(
                    "ALTER TABLE model_configs ADD COLUMN top_p FLOAT DEFAULT 0.95"
                ))
