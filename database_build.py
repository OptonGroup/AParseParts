from AvitoParser_database_version import AvitoParser
import psycopg2

import os
import dotenv

dotenv.load_dotenv()
POSTGRESQL_USER = os.getenv('POSTGRESQL_USER')
POSTGRESQL_PASSWORD = os.getenv('POSTGRESQL_PASSWORD')
AVITO_LOGIN = os.getenv('AVITO_LOGIN')
AVITO_PASSWORD = os.getenv('AVITO_PASSWORD')


class ParseBase(object):
    def __init__(self, AVITO_LOGIN, AVITO_PASSWORD, POSTGRESQL_USER, POSTGRESQL_PASSWORD):
        self.AvitoParser = AvitoParser(
            account_login=AVITO_LOGIN,
            account_password=AVITO_PASSWORD
        )
        self.base_connection = psycopg2.connect(
            dbname='avito_competitors',
            user=POSTGRESQL_USER,
            password=POSTGRESQL_PASSWORD
        )
        self.cursor = self.base_connection.cursor()

        self.excluded_users = []

    def start_parse(self):

        self.__get_search_phrases()
        self.__get_cities()

        for row_of_search_phrases in self.all_rows_of_search_phrases:
            search_phrase_id = row_of_search_phrases[0]
            item_id = row_of_search_phrases[1]
            search_phrase = row_of_search_phrases[2]

            excluded_words = self.__get_excluded_words(
                search_phrase_id=search_phrase_id
            )

            for row_of_city in self.all_rows_of_cities:
                city_id = row_of_city[0]
                city_name = row_of_city[1]

                catalog_of_ads = self.AvitoParser.parse_by_search(
                    text_search=search_phrase,
                    region=city_name
                )

                for ad in catalog_of_ads:
                    self.__process_ad(
                        ad=ad,
                        excluded_words=excluded_words,
                        search_phrase_id=search_phrase_id,
                        item_id=item_id,
                        city_id=city_id
                    )

            self.base_connection.commit()

        self.AvitoParser.close_browser()
        self.cursor.close()
        self.base_connection.close()

    def __process_ad(self, ad, excluded_words, search_phrase_id, item_id, city_id):
        is_excluded_words_in_title = any(word.lower() in ad['title'].lower() for word in excluded_words)
        is_excluded_user_name = ad['seller_name'] in self.excluded_users

        if not is_excluded_words_in_title and not is_excluded_user_name:
            self.cursor.execute(
                f"""insert into
                items_competitors_avito(search_phrase_id, item_id, name_avito, url_avito, price_avito, city_id)
                values({search_phrase_id}, {item_id}, '{ad['title']}', '{ad['url']}', {ad['price']}, {city_id});"""
            )

    def __get_cities(self):
        self.cursor.execute('SELECT * FROM cities')
        self.all_rows_of_cities = self.cursor.fetchall()

    def __get_excluded_words(self, search_phrase_id):
        self.cursor.execute(f'SELECT * FROM excluded_words WHERE search_phrase_id={search_phrase_id}')
        all_rows_of_excluded_words = self.cursor.fetchall()
        excluded_words = []
        for row_of_excluded_words in all_rows_of_excluded_words:
            excluded_words.append(row_of_excluded_words[2])
        return excluded_words

    def __get_search_phrases(self):
        self.cursor.execute('SELECT * FROM search_phrases')
        self.all_rows_of_search_phrases = self.cursor.fetchall()

    def exclude_user_by_name(self, user_name):
        self.excluded_users.append(user_name)


if __name__ == '__main__':
    parse = ParseBase(
        AVITO_LOGIN=AVITO_LOGIN,
        AVITO_PASSWORD=AVITO_PASSWORD,
        POSTGRESQL_USER=POSTGRESQL_USER,
        POSTGRESQL_PASSWORD=POSTGRESQL_PASSWORD
    )

    parse.exclude_user_by_name('LR-STUDIO')
    parse.exclude_user_by_name('LANDROVER-STUDIO')

    parse.start_parse()
