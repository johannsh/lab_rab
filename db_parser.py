from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Определяем базовый класс для таблиц
Base = declarative_base()

class wordList(Base):
    __tablename__ = 'wordList'
    
    word_id = Column(Integer, primary_key=True)
    word = Column(String)
    linkWord = relationship("linkWord", back_populates="word")

class URLList(Base):
    __tablename__ = 'URLList'
    
    url_id = Column(Integer, primary_key=True)
    URL = Column(String, unique=True)  # Убедитесь, что URL уникален

class wordLocation(Base):
    __tablename__ = 'wordLocation'
    
    wordLocation_id = Column(Integer, primary_key=True)
    fk_wordId = Column(Integer, ForeignKey('wordList.word_id'))
    fk_URLId = Column(Integer, ForeignKey('URLList.url_id'))
    location = Column(Integer)  # Может быть, это индекс или позиция слова на странице

class linkBetweenURL(Base):
    __tablename__ = 'linkBetweenURL'
    
    linkBeteenURL = Column(Integer, primary_key=True)
    fk_fromURL_id = Column(Integer, ForeignKey('URLList.url_id'))
    fk_toURL_id = Column(Integer, ForeignKey('URLList.url_id'))

class linkWord(Base):
    __tablename__ = 'linkWord'
    
    linkWord_id = Column(Integer, primary_key=True)
    fk_wordId = Column(Integer, ForeignKey('wordList.word_id'))
    fk_linkId = Column(Integer, ForeignKey('linkBetweenURL.linkBeteenURL'))
    word = relationship("wordList", back_populates="linkWord")

# Настройка подключения к базе данных (SQLite)
DATABASE_URL = "sqlite+aiosqlite:///db_parser.db"  # Используем SQLite с асинхронной библиотекой aiosqlite

# Создаем асинхронный движок
engine = create_async_engine(DATABASE_URL, echo=True)

# Создаем асинхронную сессию
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

# Функция для создания базы данных и таблиц
async def create_database_if_not_exists():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("База данных и таблицы успешно созданы!")

# Основная асинхронная функция для запуска программы
async def main():
    # Создаем базу данных, если она не существует
    await create_database_if_not_exists()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())