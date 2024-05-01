#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
メルカリから販売履歴や購入履歴を収集します．

Usage:
  crawler.py [-c CONFIG]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
"""

import logging
import random
import math
import re
import datetime
import time
import traceback

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

import store_rakuten.const
import store_rakuten.handle

import local_lib.captcha
import local_lib.selenium_util

STATUS_ORDER_COUNT = "[collect] Count of year"
STATUS_ORDER_ITEM_ALL = "[collect] All orders"
STATUS_ORDER_ITEM_BY_YEAR = "[collect] Year {year} orders"

LOGIN_RETRY_COUNT = 2
FETCH_RETRY_COUNT = 3


def wait_for_loading(handle, xpath="//body", sec=1):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    wait.until(EC.visibility_of_all_elements_located((By.XPATH, xpath)))
    time.sleep(sec)


def visit_url(handle, url, xpath="//body"):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)
    driver.get(url)

    wait_for_loading(handle, xpath)


def parse_date(date_text):
    return datetime.datetime.strptime(date_text, "%Y年%m月%d日")


def parse_datetime(date_text):
    return datetime.datetime.strptime(date_text, "%Y年%m月%d日 %H:%M")


def gen_hist_url(year, page):
    return store_rakuten.const.HIST_URL_BY_YEAR.format(year=year, page=page)


def gen_item_id_from_url(url):
    m = re.match(r"https?://item.rakuten.co.jp/([^/]+)/([^/]+)", url)

    return "{store_id}/{item_id}".format(store_id=m.group(1), item_id=m.group(2))


def gen_order_url_from_no(no):
    m = re.match(r"(\d+)-", no)
    store_id = m.group(1)

    return store_rakuten.const.ORDER_URL_BY_NO.format(store_id=store_id, no=no)


def gen_status_label_by_year(year):
    return STATUS_ORDER_ITEM_BY_YEAR.format(year=year)


def save_thumbnail(handle, item, thumb_url):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    with local_lib.selenium_util.browser_tab(driver, thumb_url):
        png_data = driver.find_element(By.XPATH, "//img").screenshot_as_png

        with open(store_rakuten.handle.get_thumb_path(handle, item), "wb") as f:
            f.write(png_data)


def fetch_item_detail_default(handle, item):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    with local_lib.selenium_util.browser_tab(driver, item["url"]):
        wait_for_loading(handle)

        breadcrumb_list = driver.find_elements(By.XPATH, '//td[@class="sdtext"]/a')
        category = list(map(lambda x: x.text, breadcrumb_list))

        if len(category) >= 1:
            category.pop(0)

        item["category"] = category


def fetch_item_detail_book(handle, item):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    with local_lib.selenium_util.browser_tab(driver, item["url"]):
        wait_for_loading(handle)

        breadcrumb_list = driver.find_elements(By.XPATH, '//dd[@itemprop="breadcrumb"]/a')
        category = list(map(lambda x: x.text, breadcrumb_list))

        if len(category) >= 1:
            category.pop(0)

        item["category"] = category


def fetch_item_detail(handle, item):
    if item["seller"] == "楽天ブックス":
        return fetch_item_detail_book(handle, item)
    else:
        return fetch_item_detail_default(handle, item)


def parse_item_book(handle, item_xpath, item_base):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    link = driver.find_element(By.XPATH, item_xpath + '//h2[contains(@class, "item-detail__title")]/a')
    name = link.text
    url = link.get_attribute("href")

    item_id = gen_item_id_from_url(url)

    price_text = driver.find_element(
        By.XPATH,
        item_xpath
        + '//div[contains(@class, "item-detail__price")]/span[contains(@class, "item-detail__price-num")]',
    ).text
    price = int(re.match(r".*?(\d{1,3}(?:,\d{3})*)", price_text).group(1).replace(",", ""))

    count = int(
        driver.find_element(
            By.XPATH,
            item_xpath
            + '//div[contains(@class, "item-detail__order")]/span[contains(@class, "item-detail__order-num")]',
        ).text
    )

    item = {
        "name": name,
        "price": price,
        "count": count,
        "url": url,
        "id": item_id,
    } | item_base

    fetch_item_detail(handle, item)

    thumb_url = driver.find_element(
        By.XPATH,
        item_xpath + '//div[contains(@class, "item-image")]//img',
    ).get_attribute("src")
    save_thumbnail(handle, item, thumb_url)

    return item


def parse_item_default(handle, item_xpath, item_base):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    link = driver.find_element(By.XPATH, item_xpath + '//td[contains(@class, "prodName")]/a')
    name = link.text
    url = link.get_attribute("href")

    item_id = gen_item_id_from_url(url)

    price_text = driver.find_element(By.XPATH, item_xpath + '//td[contains(@class, "widthPrice")]').text
    price = int(re.match(r".*?(\d{1,3}(?:,\d{3})*)", price_text).group(1).replace(",", ""))

    count = int(driver.find_element(By.XPATH, item_xpath + '//td[contains(@class, "widthQuantity")]').text)

    include_tax = driver.find_element(By.XPATH, item_xpath + '//td[contains(@class, "widthTax")]').text == "込"

    item = {
        "name": name,
        "price": price,
        "count": count,
        "url": url,
        "include_tax": include_tax,
        "id": item_id,
    } | item_base

    fetch_item_detail(handle, item)

    thumb_url = driver.find_element(
        By.XPATH,
        item_xpath + '//td[contains(@class, "prodImg")]//img',
    ).get_attribute("src")
    save_thumbnail(handle, item, thumb_url)

    return item


def parse_order_book(handle, order_info):
    ITEM_XPATH = '//div[contains(@class, "shipping-list")]//li[contains(@class, "item")]'

    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    datetime_text = driver.find_element(By.XPATH, '//div[contains(@class, "order-info__date")]').text.rsplit(
        " ", 1
    )[0]
    date = parse_datetime(datetime_text)

    no = driver.find_element(
        By.XPATH, '//div[contains(@class, "order-info__detail")]/span[contains(@class, "order-info__number")]'
    ).text

    item_base = {
        "date": date,
        "no": no,
        "seller": order_info["seller"],
    }

    is_unempty = False
    for i in range(len(driver.find_elements(By.XPATH, ITEM_XPATH))):
        item_xpath = "(" + ITEM_XPATH + ")[{index}]".format(index=i + 1)

        item = parse_item_book(handle, item_xpath, item_base)

        logging.info("{name} {price:,}円".format(name=item["name"], price=item["price"]))

        store_rakuten.handle.record_item(handle, item)
        is_unempty = True

    return is_unempty


def parse_order_default(handle, order_info):
    ITEM_XPATH = '//div[contains(@class, "oDrSpecPurchaseInfo")]//tr[contains(@valign, "top") and td[contains(@class, "prodInfo")]]'

    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    date_text = driver.find_element(
        By.XPATH, '//div[contains(@class, "oDrSpecOrderInfo")]//td[contains(@class, "orderDate")]'
    ).text
    date = parse_date(date_text)

    no = driver.find_element(
        By.XPATH, '//div[contains(@class, "oDrSpecOrderInfo")]//td[contains(@class, "orderID")]'
    ).text

    item_base = {
        "date": date,
        "no": no,
        "seller": order_info["seller"],
    }

    is_unempty = False
    for i in range(len(driver.find_elements(By.XPATH, ITEM_XPATH))):
        item_xpath = "(" + ITEM_XPATH + ")[{index}]".format(index=i + 1)

        item = parse_item_default(handle, item_xpath, item_base)

        logging.info("{name} {price:,}円".format(name=item["name"], price=item["price"]))

        store_rakuten.handle.record_item(handle, item)
        is_unempty = True

    return is_unempty


def parse_order(handle, order_info):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    logging.info(
        "Parse order: {date} - {seller} - {no}".format(
            date=order_info["date"].strftime("%Y-%m-%d"),
            seller=order_info["seller"],
            no=order_info["no"],
        )
    )

    if local_lib.selenium_util.xpath_exists(driver, '//ul[contains(@class, "mypage_cxl_mordal_text_error")]'):
        logging.warning(
            "Error occured: {message}".format(
                message=driver.find_element(
                    By.XPATH, '//ul[contains(@class, "mypage_cxl_mordal_text_error")]'
                ).text
            )
        )

        return False

    if order_info["seller"] == "楽天ブックス":
        is_unempty = parse_order_book(handle, order_info)
    else:
        is_unempty = parse_order_default(handle, order_info)

    return is_unempty


def fetch_order_item_list_by_order_info(handle, order_info):
    visit_url(handle, order_info["url"])
    keep_logged_on(handle)

    if not parse_order(handle, order_info):
        logging.warning("Failed to parse order of {no}".format(no=order_info["no"]))
        time.sleep(1)
        return False

    return True


def skip_order_item_list_by_year_page(handle, year, page):
    logging.info("Skip check order of {year} page {page} [cached]".format(year=year, page=page))
    incr_order = min(
        store_rakuten.handle.get_order_count(handle, year)
        - store_rakuten.handle.get_progress_bar(handle, gen_status_label_by_year(year)).count,
        store_rakuten.const.ORDER_COUNT_PER_PAGE,
    )
    store_rakuten.handle.get_progress_bar(handle, gen_status_label_by_year(year)).update(incr_order)
    store_rakuten.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update(incr_order)

    # NOTE: これ，状況によっては最終ページで成り立たないので，良くない
    return incr_order != store_rakuten.const.ORDER_COUNT_PER_PAGE


def fetch_order_item_list_by_year_page(handle, year, page, retry=0):
    ORDER_DATE_XPATH = '//div[contains(@class, "oDrListItem") and table]'

    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    total_page = math.ceil(
        store_rakuten.handle.get_order_count(handle, year) / store_rakuten.const.ORDER_COUNT_PER_PAGE
    )

    store_rakuten.handle.set_status(
        handle,
        "注文履歴を解析しています... {year}年 {page}/{total_page} ページ".format(year=year, page=page, total_page=total_page),
    )

    visit_url(handle, gen_hist_url(year, page))
    keep_logged_on(handle)

    logging.info(
        "Check order of {year} page {page}/{total_page}".format(year=year, page=page, total_page=total_page)
    )
    logging.info("URL: {url}".format(url=driver.current_url))

    order_list = []
    for i in range(len(driver.find_elements(By.XPATH, ORDER_DATE_XPATH))):
        order_xpath = "(" + ORDER_DATE_XPATH + "[{index}])".format(index=i + 1)

        date_text = driver.find_element(By.XPATH, order_xpath + '//li[contains(@class, "purchaseDate")]').text
        date = parse_date(date_text)

        if not local_lib.selenium_util.xpath_exists(
            driver, order_xpath + "//li[contains(@class, 'orderID')]/span[contains(@class, 'idNum')]"
        ):
            logging.warning("Failed to detect orderID")
            continue

        no = driver.find_element(
            By.XPATH,
            order_xpath + "//li[contains(@class, 'orderID')]/span[contains(@class, 'idNum')]",
        ).text

        seller = driver.find_element(By.XPATH, order_xpath + "//li[contains(@class, 'shopName')]/a").text

        url = driver.find_element(
            By.XPATH, order_xpath + "//li[contains(@class, 'oDrDetailList')]/a"
        ).get_attribute("href")

        order_list.append({"date": date, "no": no, "url": url, "seller": seller})

    time.sleep(1)

    for order_info in order_list:
        if not store_rakuten.handle.get_order_stat(handle, order_info["no"]):
            fetch_order_item_list_by_order_info(handle, order_info)
        else:
            logging.info(
                "Done order: {date} - {no} [cached]".format(
                    date=order_info["date"].strftime("%Y-%m-%d"), no=order_info["no"]
                )
            )

        store_rakuten.handle.get_progress_bar(handle, gen_status_label_by_year(year)).update()
        store_rakuten.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update()

        if year == datetime.datetime.now().year:
            last_item = store_rakuten.handle.get_last_item(handle, year)
            if (
                store_rakuten.handle.get_year_checked(handle, year)
                and (last_item != None)
                and (last_item["no"] == order_info["no"])
            ):
                logging.info("Latest order found, skipping analysis of subsequent pages")
                for i in range(total_page):
                    store_rakuten.handle.set_page_checked(handle, year, i + 1)

    return page >= total_page


def fetch_order_item_list_by_year(handle, year, start_page=1):
    visit_url(handle, gen_hist_url(year, start_page))
    keep_logged_on(handle)

    year_list = store_rakuten.handle.get_year_list(handle)

    logging.info(
        "Check order of {year} ({year_index}/{total_year})".format(
            year=year, year_index=year_list.index(year) + 1, total_year=len(year_list)
        )
    )

    store_rakuten.handle.set_progress_bar(
        handle,
        gen_status_label_by_year(year),
        store_rakuten.handle.get_order_count(handle, year),
    )

    page = start_page
    while True:
        if not store_rakuten.handle.get_page_checked(handle, year, page):
            is_last = fetch_order_item_list_by_year_page(handle, year, page)
            store_rakuten.handle.set_page_checked(handle, year, page)
        else:
            is_last = skip_order_item_list_by_year_page(handle, year, page)

        store_rakuten.handle.store_order_info(handle)

        if is_last:
            break

        page += 1

    store_rakuten.handle.get_progress_bar(handle, gen_status_label_by_year(year)).update()

    store_rakuten.handle.set_year_checked(handle, year)


def fetch_year_list(handle):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    visit_url(handle, store_rakuten.const.HIST_URL)

    keep_logged_on(handle)

    year_list = list(
        sorted(
            map(
                lambda elem: int(elem.get_attribute("value")),
                driver.find_elements(
                    By.XPATH, '//select[@id="selectPeriodYear"]/option[contains(@value, "20")]'
                ),
            )
        )
    )

    store_rakuten.handle.set_year_list(handle, year_list)

    logging.info(year_list)

    return year_list


def fetch_order_count_by_year(handle, year):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    store_rakuten.handle.set_status(handle, "注文件数を調べています... {year}年".format(year=year))

    visit_url(handle, gen_hist_url(year, 1))

    if local_lib.selenium_util.xpath_exists(driver, '//div[contains(@class, "noItem")]'):
        return 0

    return int(
        driver.find_element(
            By.XPATH, '//div[contains(@class, "oDrPager")]//span[contains(@class, "totalItem")]'
        ).text
    )


def fetch_order_count(handle):
    year_list = store_rakuten.handle.get_year_list(handle)

    logging.info("Collect order count")

    store_rakuten.handle.set_progress_bar(handle, STATUS_ORDER_COUNT, len(year_list))

    total_count = 0
    for year in year_list:
        if year >= store_rakuten.handle.get_cache_last_modified(handle).year:
            count = fetch_order_count_by_year(handle, year)
            store_rakuten.handle.set_order_count(handle, year, count)
            logging.info("Year {year}: {count:4,} orders".format(year=year, count=count))
        else:
            count = store_rakuten.handle.get_order_count(handle, year)
            logging.info("Year {year}: {count:4,} orders [cached]".format(year=year, count=count))

        total_count += count
        store_rakuten.handle.get_progress_bar(handle, STATUS_ORDER_COUNT).update()

    logging.info("Total order is {total_count:,}".format(total_count=total_count))

    store_rakuten.handle.get_progress_bar(handle, STATUS_ORDER_COUNT).update()
    store_rakuten.handle.store_order_info(handle)


def fetch_order_item_list_all_year(handle):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    year_list = fetch_year_list(handle)
    fetch_order_count(handle)

    store_rakuten.handle.set_progress_bar(
        handle, STATUS_ORDER_ITEM_ALL, store_rakuten.handle.get_total_order_count(handle)
    )

    for year in year_list:
        if (
            (year == datetime.datetime.now().year)
            or (year == store_rakuten.handle.get_cache_last_modified(handle).year)
            or (not store_rakuten.handle.get_year_checked(handle, year))
        ):
            fetch_order_item_list_by_year(handle, year)
        else:
            logging.info(
                "Done order of {year} ({year_index}/{total_year}) [cached]".format(
                    year=year, year_index=year_list.index(year) + 1, total_year=len(year_list)
                )
            )
            store_rakuten.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update(
                store_rakuten.handle.get_order_count(handle, year)
            )

    store_rakuten.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update()


def fetch_order_item_list(handle):
    store_rakuten.handle.set_status(handle, "巡回ロボットの準備をします...")
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    store_rakuten.handle.set_status(handle, "注文履歴の収集を開始します...")

    try:
        fetch_order_item_list_all_year(handle)
    except:
        local_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), store_rakuten.handle.get_debug_dir_path(handle)
        )
        raise

    store_rakuten.handle.set_status(handle, "注文履歴の収集が完了しました．")


def execute_login(handle):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    driver.find_element(By.XPATH, '//input[@id="loginInner_u"]').clear()
    driver.find_element(By.XPATH, '//input[@id="loginInner_u"]').send_keys(
        store_rakuten.handle.get_login_user(handle)
    )
    driver.find_element(By.XPATH, '//input[@id="loginInner_p"]').send_keys(
        store_rakuten.handle.get_login_pass(handle)
    )

    local_lib.selenium_util.click_xpath(driver, '//input[@name="submit"]')

    wait_for_loading(handle)


def keep_logged_on(handle):
    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    wait_for_loading(handle)

    if not local_lib.selenium_util.xpath_exists(driver, '//table[contains(@class, "loginBox")]'):
        return

    logging.info("Try to login")

    for i in range(LOGIN_RETRY_COUNT):
        if i != 0:
            logging.info("Retry to login")

        execute_login(handle)

        wait_for_loading(handle)

        if not local_lib.selenium_util.xpath_exists(driver, '//table[contains(@class, "loginBox")]'):
            return

        logging.warning("Failed to login")

        local_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),
            store_rakuten.handle.get_debug_dir_path(handle),
        )

    logging.error("Give up to login")
    raise Exception("ログインに失敗しました．")


if __name__ == "__main__":
    from docopt import docopt

    import local_lib.logger
    import local_lib.config

    args = docopt(__doc__)

    local_lib.logger.init("test", level=logging.INFO)

    config = local_lib.config.load(args["-c"])
    handle = store_rakuten.handle.create(config)

    driver, wait = store_rakuten.handle.get_selenium_driver(handle)

    try:
        fetch_order_item_list(handle)
    except:
        driver, wait = store_rakuten.handle.get_selenium_driver(handle)
        logging.error(traceback.format_exc())

        local_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),
            store_rakuten.handle.get_debug_dir_path(handle),
        )
