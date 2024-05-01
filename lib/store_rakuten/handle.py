#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib
import enlighten
import datetime
import functools

from selenium.webdriver.support.wait import WebDriverWait
import openpyxl.styles

import local_lib.serializer
import local_lib.selenium_util


def create(config):
    handle = {
        "progress_manager": enlighten.get_manager(),
        "progress_bar": {},
        "config": config,
    }

    load_order_info(handle)

    prepare_directory(handle)

    return handle


def get_login_user(handle):
    return handle["config"]["login"]["rakuten"]["user"]


def get_login_pass(handle):
    return handle["config"]["login"]["rakuten"]["pass"]


def prepare_directory(handle):
    get_selenium_data_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_debug_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_thumb_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_caceh_file_path(handle).parent.mkdir(parents=True, exist_ok=True)
    get_excel_file_path(handle).parent.mkdir(parents=True, exist_ok=True)


def get_excel_font(handle):
    font_config = handle["config"]["output"]["excel"]["font"]
    return openpyxl.styles.Font(name=font_config["name"], size=font_config["size"])


def get_caceh_file_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["rakuten"]["cache"]["order"])


def get_excel_file_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["output"]["excel"]["table"])


def get_thumb_dir_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["rakuten"]["cache"]["thumb"])


def get_selenium_data_dir_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["selenium"])


def get_debug_dir_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["debug"])


def get_selenium_driver(handle):
    if "selenium" in handle:
        return (handle["selenium"]["driver"], handle["selenium"]["wait"])
    else:
        driver = local_lib.selenium_util.create_driver("Rakhist", get_selenium_data_dir_path(handle))
        wait = WebDriverWait(driver, 5)

        local_lib.selenium_util.clear_cache(driver)

        handle["selenium"] = {
            "driver": driver,
            "wait": wait,
        }

        return (driver, wait)


def record_item(handle, item):
    handle["order"]["item_list"].append(item)
    handle["order"]["order_no_stat"][item["no"]] = True


def get_order_stat(handle, no):
    return no in handle["order"]["order_no_stat"]


def get_item_list(handle):
    return sorted(handle["order"]["item_list"], key=lambda x: x["date"])


def get_last_item(handle, year):
    return next(filter(lambda item: item["date"].year == year, reversed(get_item_list(handle))), None)


def set_year_list(handle, year_list):
    handle["order"]["year_list"] = year_list


def get_year_list(handle):
    return handle["order"]["year_list"]


def set_order_count(handle, year, order_count):
    handle["order"]["year_count"][year] = order_count


def set_page_checked(handle, year, page):
    if year in handle["order"]["page_stat"]:
        handle["order"]["page_stat"][year][page] = True
    else:
        handle["order"]["page_stat"][year] = {page: True}


def get_page_checked(handle, year, page):
    if (year in handle["order"]["page_stat"]) and (page in handle["order"]["page_stat"][year]):
        return handle["order"]["page_stat"][year][page]
    else:
        return False


def set_year_checked(handle, year):
    handle["order"]["year_stat"][year] = True
    store_order_info(handle)


def get_year_checked(handle, year):
    return year in handle["order"]["year_stat"]


def get_order_count(handle, year):
    return handle["order"]["year_count"][year]


def get_total_order_count(handle):
    return functools.reduce(lambda a, b: a + b, handle["order"]["year_count"].values())


def get_thumb_path(handle, item):
    (get_thumb_dir_path(handle) / item["id"]).parent.mkdir(parents=True, exist_ok=True)

    return get_thumb_dir_path(handle) / (item["id"] + ".png")


def get_cache_last_modified(handle):
    return handle["order"]["last_modified"]


def set_progress_bar(handle, desc, total):
    BAR_FORMAT = (
        "{desc:31s}{desc_pad}{percentage:3.0f}% |{bar}| {count:5d} / {total:5d} "
        + "[{elapsed}<{eta}, {rate:6.2f}{unit_pad}{unit}/s]"
    )
    COUNTER_FORMAT = (
        "{desc:30s}{desc_pad}{count:5d} {unit}{unit_pad}[{elapsed}, {rate:6.2f}{unit_pad}{unit}/s]{fill}"
    )

    handle["progress_bar"][desc] = handle["progress_manager"].counter(
        total=total, desc=desc, bar_format=BAR_FORMAT, counter_format=COUNTER_FORMAT
    )


def set_status(handle, status, is_error=False):
    if is_error:
        color = "bold_bright_white_on_red"
    else:
        color = "bold_bright_white_on_lightslategray"

    if "status" not in handle:
        handle["status"] = handle["progress_manager"].status_bar(
            status_format="楽天{fill}{status}{fill}{elapsed}",
            color=color,
            justify=enlighten.Justify.CENTER,
            status=status,
        )
    else:
        handle["status"].color = color
        handle["status"].update(status=status, force=True)


def finish(handle):
    if "selenium" in handle:
        handle["selenium"]["driver"].quit()
        handle.pop("selenium")

    handle["progress_manager"].stop()


def store_order_info(handle):
    handle["order"]["last_modified"] = datetime.datetime.now()

    local_lib.serializer.store(get_caceh_file_path(handle), handle["order"])


def load_order_info(handle):
    handle["order"] = local_lib.serializer.load(
        get_caceh_file_path(handle),
        {
            "year_list": [],
            "year_count": {},
            "year_stat": {},
            "page_stat": {},
            "item_list": [],
            "order_no_stat": {},
            "last_modified": datetime.datetime(1994, 7, 5),
        },
    )

    # NOTE: 再開した時には巡回すべきなので削除しておく
    for year in [
        datetime.datetime.now().year,
        get_cache_last_modified(handle).year,
    ]:
        if year in handle["order"]["page_stat"]:
            del handle["order"]["page_stat"][year]


def get_progress_bar(handle, desc):
    return handle["progress_bar"][desc]
