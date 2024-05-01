#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
楽天の購入履歴情報をエクセルファイルに書き出します．

Usage:
  order_history.py [-c CONFIG] [-o EXCEL] [-N]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -o EXCEL      : 生成する Excel ファイルを指定します．[default: rakhist.xlsx]
  -N            : サムネイル画像を含めないようにします．
"""

import logging

import openpyxl
import openpyxl.utils
import openpyxl.styles
import openpyxl.drawing.image
import openpyxl.drawing.xdr
import openpyxl.drawing.spreadsheet_drawing

import local_lib.openpyxl_util
import store_rakuten.handle
import store_rakuten.crawler

STATUS_INSERT_ITEM = "[generate] Insert item"
STATUS_ALL = "[generate] Excel file"

SHOP_NAME = "楽天"

SHEET_DEF = {
    "SHEET_TITLE": "【{shop_name}】購入".format(shop_name=SHOP_NAME),
    "TABLE_HEADER": {
        "row": {
            "pos": 2,
            "height": {"default": 80, "without_thumb": 25},
        },
        "col": {
            "shop_name": {
                "label": "ショップ",
                "pos": 2,
                "width": 15,
                "format": "@",
                "value": SHOP_NAME,
            },
            "date": {
                "label": "日付",
                "pos": 3,
                "width": 23,
                "format": 'yyyy"年"mm"月"dd"日 ("aaa")"',
            },
            "name": {
                "label": "商品名",
                "pos": 4,
                "width": 70,
                "wrap": True,
                "format": "@",
            },
            "image": {
                "label": "画像",
                "pos": 5,
                "width": 12,
            },
            "count": {
                "label": "数量",
                "pos": 6,
                "format": "0_ ",
                "width": 8,
            },
            "price": {
                "label": "価格",
                "pos": 7,
                "width": 16,
                "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
            },
            "category": {
                "label": "カテゴリ",
                "pos": 8,
                "length": 3,
                "width": 20,
                "wrap": True,
            },
            "seller": {
                "label": "ストア",
                "pos": 11,
                "width": 29,
                "format": "@",
                "wrap": True,
            },
            "id": {
                "label": "商品ID",
                "pos": 12,
                "width": 17,
                "format": "@",
                "wrap": True,
                "link_func": lambda item: item["url"],
            },
            "no": {
                "label": "注文番号",
                "pos": 13,
                "width": 28,
                "format": "@",
                "wrap": True,
                "link_func": lambda item: store_rakuten.crawler.gen_order_url_from_no(item["no"]),
            },
        },
    },
}


def generate_sheet(handle, book, is_need_thumb=True):
    item_list = store_rakuten.handle.get_item_list(handle)

    store_rakuten.handle.set_progress_bar(handle, STATUS_INSERT_ITEM, len(item_list))

    local_lib.openpyxl_util.generate_list_sheet(
        book,
        item_list,
        SHEET_DEF,
        is_need_thumb,
        lambda item: store_rakuten.handle.get_thumb_path(handle, item),
        lambda status: store_rakuten.handle.set_status(handle, status),
        lambda: store_rakuten.handle.get_progress_bar(handle, STATUS_ALL).update(),
        lambda: store_rakuten.handle.get_progress_bar(handle, STATUS_INSERT_ITEM).update(),
    )


def generate_table_excel(handle, excel_file, is_need_thumb=True):
    store_rakuten.handle.set_status(handle, "エクセルファイルの作成を開始します...")
    store_rakuten.handle.set_progress_bar(handle, STATUS_ALL, 5)

    logging.info("Start to Generate excel file")

    book = openpyxl.Workbook()
    book._named_styles["Normal"].font = store_rakuten.handle.get_excel_font(handle)

    store_rakuten.handle.get_progress_bar(handle, STATUS_ALL).update()

    generate_sheet(handle, book, is_need_thumb)

    book.remove(book.worksheets[0])

    store_rakuten.handle.set_status(handle, "エクセルファイルを書き出しています...")

    book.save(excel_file)

    store_rakuten.handle.get_progress_bar(handle, STATUS_ALL).update()

    book.close()

    store_rakuten.handle.get_progress_bar(handle, STATUS_ALL).update()

    store_rakuten.handle.set_status(handle, "完了しました！")

    logging.info("Complete to Generate excel file")


if __name__ == "__main__":
    from docopt import docopt

    import local_lib.logger
    import local_lib.config

    args = docopt(__doc__)

    local_lib.logger.init("test", level=logging.INFO)

    config = local_lib.config.load(args["-c"])
    excel_file = args["-o"]
    is_need_thumb = not args["-N"]

    handle = store_rakuten.handle.create(config)

    generate_table_excel(handle, excel_file, is_need_thumb)

    store_rakuten.handle.finish(handle)
