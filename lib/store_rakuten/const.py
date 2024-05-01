#!/usr/bin/env python3
# -*- coding: utf-8 -*-

HIST_URL = "https://order.my.rakuten.co.jp/"

HIST_URL_BY_YEAR = (
    "https://order.my.rakuten.co.jp/?"
    + "page=myorder&act=list&display_span={year}&display_month=0&page_num={page}"
)

ORDER_URL_BY_NO = (
    "https://order.my.rakuten.co.jp/?page=myorder&act=detail_view&shop_id={store_id}&order_number={no}"
)


ORDER_COUNT_PER_PAGE = 25
