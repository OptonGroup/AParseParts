import os
from pprint import pprint

import dotenv
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
import json
import time

from regions_ids import REGIONS

dotenv.load_dotenv()

AVITO_LOGIN = os.getenv('AVITO_LOGIN')
AVITO_PASSWORD = os.getenv('AVITO_PASSWORD')


class AvitoParser(object):
    def __init__(self, account_login, account_password):
        """
            * Передаваемые переменные:
                account_login - телефон/почта от аккаунта avito.ru | данные в формате строки
                account_password - пароль от аккаунта avito.ru | данные в формате строки

            * Описание функции:
                - создаётся список в формате [РЕГИОН -> ID для авито]
                - создаётся сессия selenium
                - настривается сесия для оптимального парсинга (без загрузки изображений и js скриптов)
                - происходит вход в аккаунт avito (для обхода блокировок)
        """

        # получаем для каждого региона и города свой id
        self.regions_id = REGIONS

        # создаём настройки для сессии
        options = uc.ChromeOptions()
        options.add_argument("--disable-extensions")
        options.experimental_options["prefs"] = {
            # 'profile.managed_default_content_settings.javascript': 2,
            'profile.managed_default_content_settings.images': 2,
            'profile.managed_default_content_settings.mixed_script': 2,
            'profile.managed_default_content_settings.media_stream': 2,
            'profile.managed_default_content_settings.stylesheets': 2
        }

        self.browser = uc.Chrome(options=options)

        # производим вход в аккаунт avito
        self.browser.get(url='https://www.avito.ru/#login?authsrc=h')
        time.sleep(6)
        self.browser.find_element(By.NAME, 'login').send_keys(account_login)
        time.sleep(1)
        self.browser.find_element(By.NAME, 'password').send_keys(account_password)
        time.sleep(0.5)
        self.browser.find_element(By.NAME, 'submit').click()
        time.sleep(4)

        # выключить загрузку *.js и *.css файлов для более быстрой загрузки страниц
        self.browser.execute_cdp_cmd('Network.setBlockedURLs', {'urls': ['*.js', '*.css']})
        self.browser.execute_cdp_cmd('Network.enable', {})

    def __parse_ad_information(self, url_to_ad):
        """
            * Передаваемые переменные:
                url_to_ad - ссылка на объявление, информацию с которого нужно собрать

            * Описание функции:
                - создаётся словарь ad_info, где хранится информация с объявления
                - парсится название, описание, цена, имя продавца, состояние, количество просмотров
        """

        ad_info = {
            'title': '',
            'description': '',
            'price': 0,
            'seller_name': '',
            'condition': '',
            'views': 0,
        }

        try:
            # открываем объявление, берём с него html код
            self.browser.get(url=url_to_ad)
            soup = BeautifulSoup(self.browser.page_source, 'html.parser')

            # берём необходимую информацию
            ad_info['title'] = soup.find('h1', {'data-marker': 'item-view/title-info'}).text
            ad_info['description'] = soup.find('div', {'data-marker': 'item-view/item-description'}).text
            ad_info['price'] = int(soup.find('span', {'data-marker': 'item-view/item-price'}).attrs['content'])
            ad_info['seller_name'] = soup.find('div', {'data-marker': 'seller-info/name'}).text
            ad_info['views'] = soup.find('span', {'data-marker': 'item-view/total-views'}).text.split()[0]

            params = soup.find_all('li', {'class': 'params-paramsList__item-_2Y2O'})
            for param in params:
                if 'Состояние' in param.text and 'Нов' in param.text:
                    ad_info['condition'] = 'Новое'
                    break
        except:
            pass

        return ad_info

    def close_browser(self):
        """
            * Описание функции:
                - Закрыть браузер (Обязательно выполнять после полного выполнения функций класса)
        """
        self.browser.close()

    def parse_by_search(self, text_search, region='Все регионы'):
        """
            * Передаваемые переменные:
                text_search - текст, который парсер будет искать в названиях объявлений
                region - региона поиска на русском языке

            * Описание функции:
                - получаем через api avito ссылки на объявления, которые будут подходить по параметрам:
                    - text_search содержится в названии
                    - объявление находится в том регионе, который был указан в region
                    - цена от 1 рубля
                - если объявление подходит под все критерии, то оно записывается в окончательный список
        """

        region_id = self.regions_id[region]
        catalog_of_ads = []
        page_number = 1

        # парсим страницы пока объявления не закончатся
        while True:
            # получаем по api объявления которые соответствуют text_search, region, от 1 рубля
            url = f'https://www.avito.ru/web/1/js/items?name={text_search}&p={page_number}&locationId={region_id}&bt=1&pmin=1&cd=0&localPriority=1&subscription%5Bvisible%5D=true&subscription%5BisShowSavedTooltip%5D=false&subscription%5BisErrorSaved%5D=false&subscription%5BisAuthenticated%5D=true'
            self.browser.get(url=url)
            content = json.loads(BeautifulSoup(self.browser.page_source, 'html.parser').find('pre').text)
            ads = content['catalog']['items']
            if len(ads) == 0:
                break

            # обрабатываем объявления
            for ad in ads:
                if ad['type'] != 'item':
                    continue
                link_to_ad = 'https://www.avito.ru' + ad['urlPath']

                # получаем всю оставшуюся информацию о объявлении
                ad_info = self.__parse_ad_information(url_to_ad=link_to_ad)
                if ad_info['condition'] != 'Новое':
                    continue

                catalog_of_ads.append({
                    'Название объявления': ad_info['title'],
                    'Описание': ad_info['description'],
                    'Цена': ad_info['price'],
                    'Имя продавца': ad_info['seller_name'],
                    'Кол-во просмотров': ad_info['views'],
                    'Ссылка': link_to_ad,
                })
            page_number += 1

        return catalog_of_ads

    def parse_shop(self, url_shop):
        """
            * Передаваемые переменные:
                url_shop - ссылка на магазин, с которого нужно получить все объявления

            * Описание функции:
                - получаем все объявления продавца
                - добавляем их в список
        """

        # получить хеш продавца из ссылки на магазин
        user_hash = ''
        splitten_url = url_shop.split('/')
        for ind in range(len(splitten_url)):
            if 'avito' in splitten_url[ind]:
                user_hash = splitten_url[ind + 2]
                break
        if not user_hash:
            return []

        catalog_of_ads = []
        offset = 0

        # парсим страницы пока объявления не закончатся
        while True:
            # получаем объявления
            url = f'https://www.avito.ru/web/1/profile/public/items?hashUserId={user_hash}&shortcut=active&offset={offset}&limit=100'
            self.browser.get(url=url)
            content = json.loads(BeautifulSoup(self.browser.page_source, 'html.parser').find('pre').text)
            ads = content['result']['list']
            if len(ads) == 0:
                break

            # обрабатываем объявления
            for ad in ads:
                link_to_ad = 'https://www.avito.ru' + ad['url']

                ad_info = self.__parse_ad_information(url_to_ad=link_to_ad)

                catalog_of_ads.append({
                    'Название объявления': ad_info['title'],
                    'Описание': ad_info['description'],
                    'Цена': ad_info['price'],
                    'Имя продавца': ad_info['seller_name'],
                    'Кол-во просмотров': ad_info['views'],
                    'Ссылка': link_to_ad,
                })
            offset += 100

        return catalog_of_ads


if __name__ == '__main__':
    test_variable = AvitoParser(account_login=AVITO_LOGIN, account_password=AVITO_PASSWORD)
    time_start = time.time()
    pprint(test_variable.regions_id)
    info_search = test_variable.parse_by_search(text_search='Фары Range Rover 2010', region='Москва')
    # info_shop = test_variable.parse_shop(
    #     url_shop='https://www.avito.ru/user/a43b7a7e9992eabd892b62f44ae4c412/profile/all?src=search_seller_info&sellerId=a43b7a7e9992eabd892b62f44ae4c412')
    # test_variable.close_browser()
    with open('content.json', 'w', encoding='utf-8') as f:
        json.dump(info_search, f, ensure_ascii=False, indent=4)
    print('Времени затрачено:', time.time() - time_start)
