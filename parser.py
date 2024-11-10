import asyncio
from copy import deepcopy
import validators  # Импортирует библиотеку Validators
from aiohttp import ClientSession
from bs4 import BeautifulSoup  # Импортирует библиотеку BeautifulSoup4
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db_parser import wordList, URLList, wordLocation, linkBetweenURL, linkWord, AsyncSessionLocal


class Crawler:
    def __init__(self, db_session: AsyncSession) -> None:
        """1. Инициализирует паука с параметрами БД."""
        self._db_session = db_session
        self._parsing_res: dict = {}
    
    def __del__(self) -> None:
        """2. Запускает деструктор."""
        """Хотим чтобы очищалась БД после закрытия программы?"""
        pass
    
    async def addIndex(self, soup: BeautifulSoup, url: str) -> list:
        """3. Индексирует одну страницу."""
        index = []
        for a_tag in soup.find_all('a'):
            link = a_tag.get('href')
            if link and validators.url(link):
                index.append(link)
        return index
    
    def getTextOnly(self, soup: BeautifulSoup) -> list:
        """4. Получает текст alt атрибута."""
        raw_alts = soup.find_all('img', alt = True)
        alts_list = []
        for alt in raw_alts:
            alt_tag = alt.get('alt')
            if alt_tag and alt_tag != ' ':  # использовать регулярные выражния?
                # self._db_cursor.execute('INSERT INTO wordList (word) VALUES (?)', (alt_tag, ))
                # self._db_connect.commit()
                alts_list.append(alt_tag)
        return alts_list

    async def isIndexed(self, url: str) -> bool:
        """5. Проверяет, был ли URL уже индексирован (асинхронно)."""
        async with self._db_session() as session:
        # Асинхронный запрос для проверки существования URL
            result = await session.execute(select(URLList).filter_by(URL=url))
        return result.scalar() is not None

    async def fetchWithSession(self, url: str, session: ClientSession, results: dict) -> None:
        """6. Отправка запроса и получение результата."""
        try:
            async with session.get(url, timeout=1) as response:
                response = await response.text()
                results[url] = response
        except Exception as e:
            print(f"Ошибка: {e}")

    async def fetchUrls(self, url_list: list[str]) -> dict[str, str]:
        """7. Отправка запроса и получение результата."""
        results = {}
        async with ClientSession() as session:
            tasks = []
            for url in url_list:
                if await self.isIndexed(url):
                    continue
                tasks.append(self.fetchWithSession(url, session, results))
            await asyncio.gather(*tasks)
        return results

    async def parseUrls(self, url_list: list[str]) -> None:
        """8. Парсит страницы и сохраняет результат."""
        url_couner = 1
        fetch_result = await self.fetchUrls(url_list)  # получение ответа по всем ссылкам
        
        for url, response in fetch_result.items():
            print(f"- {url_couner} / { len(url_list) } try {url} ...")

            soup = BeautifulSoup(response, 'html.parser')
            index = await self.addIndex(soup=soup, url=url)
            alt_list = self.getTextOnly(soup)

            self._parsing_res[url] = {'links': index, 'tags': alt_list}
            url_couner += 1

    async def crawler(self, url_list: list[str], max_depth: int = 1):
        """9. Метод сбора данных. Начиная с заданного списка страниц,
            выполняет поиск в ширину до заданной глубины, индексируя все
            встречающеся по пути страницы."""
        curr_depth = 1
        await self.parseUrls(url_list)
        while curr_depth < max_depth:
            temp_db = deepcopy(self._parsing_res)
            for url in temp_db.values():
                await self.parseUrls(url['links'])   
            curr_depth += 1

async def insertDb(parsing_res: dict):
    async with AsyncSessionLocal() as session:
        try:
            for url, data in parsing_res.items():
                # Вставляем новый URL
                new_url = URLList(URL=url)
                session.add(new_url)
                await session.commit()  # Сохраняем изменения

                # Вставляем теги для каждого URL
                url_obj = await session.execute(select(URLList).filter_by(URL=url))
                url_instance = url_obj.scalar_one()

                for tag_name in data['tags']:
                    # Проверяем, существует ли уже тег
                    existing_tag = await session.execute(select(wordList).filter_by(word=tag_name))
                    tag_instance = existing_tag.scalar_one_or_none()

                    # Если тег не найден, добавляем его
                    if not tag_instance:
                        new_tag = wordList(word=tag_name)
                        session.add(new_tag)
                        await session.commit()
                        tag_instance = new_tag

                    # Связываем тег с URL в таблице wordLocation
                    new_word_location = wordLocation(fk_wordId=tag_instance.word_id, fk_URLId=url_instance.url_id, location=1)
                    session.add(new_word_location)
                    await session.commit()

                # Вставляем ссылки (link) в таблицу linkBetweenURL
                for link in data['links']:
                    existing_link = await session.execute(
                        select(linkBetweenURL).filter_by(fk_fromURL_id=url_instance.url_id, fk_toURL_id=link)
                    )
                    link_instance = existing_link.scalar_one_or_none()

                    if not link_instance:
                        new_link = linkBetweenURL(fk_fromURL_id=url_instance.url_id, fk_toURL_id=link)
                        session.add(new_link)
                        await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"Ошибка при вставке данных: {e}")
        #     existing_link = session.query(URLList)
            
        # session.commit()
        

        #     existing_tag = session.query(wordList)
            

        # link = self._parsing_res
        # stmt = insert(URLList).values(URL=link)
        # try:
        #     self._db_session.execute(stmt)  # Выполнение запроса
        #     self._db_session.commit()  # Сохранение изменений в базе данных
        #     print(f"Добавлена ссылка: {link}")
        # except Exception as e:
        #     print(f"Ошибка при добавлении ссылки {link}: {e}")
        #     self._db_session.rollback()  # Откат в случае ошибки

if __name__ == "__main__":
    """0. Программа начинает работать."""
    
    url_list = [
        'https://www.tadviser.ru/index.php/%D0%90%D0%BD%D0%B0%D0%BB%D0%B8%D1%82%D0%B8%D0%BA%D0%B0_TAdviser',
        'https://www.roscosmos.ru/115',
        'https://habr.com/ru/articles/846664/',
    ]
     
    async_session = AsyncSessionLocal()

    firstCrawler = Crawler(db_session=AsyncSessionLocal)

    # Запускаем event loop для организации асинхронных запросов к URL-ам
    asyncio.run(
        firstCrawler.crawler(
            url_list=url_list,
            max_depth=3,
        ),
    )

    # Вставляем все собранные данные в базу данных
    asyncio.run(insertDb(firstCrawler._parsing_res))