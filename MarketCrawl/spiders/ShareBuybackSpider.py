# -*- coding: utf-8 -*-
from scrapy.spiders import Spider
from scrapy.http import Request
from scrapy.http import Response
from scrapy import signals
from collections import OrderedDict
from MarketCrawl.logger import logger
from MarketCrawl.items import *
import time
import pytz
import datetime
import demjson
import re
import random
import string

class ShareBuybackSpider(Spider):
    name = 'ShareBuybackSpider'
    allowed_domains = ['api.dataide.eastmoney.com',]
    start_urls = ['http://api.dataide.eastmoney.com/data/gethglist']

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(s.spider_closed, signal=signals.spider_closed)
        return s

    def spider_opened(self, spider):
        assert isinstance(spider, Spider)
        logger.info('###############################%s Start###################################', spider.name)

    def spider_closed(self, spider):
        assert isinstance(spider, Spider)
        logger.info('###############################%s End#####################################', spider.name)

    @staticmethod
    # 生成一个指定长度的随机字符串
    def generate_random_prefix(length=8):
        str_list = [random.choice(string.digits + string.ascii_letters) for i in range(length)]
        random_str = ''.join(str_list)
        return random_str

    @staticmethod
    def transfrom_beijing_time(time_second=int(time.time())):
        # 设置为东八区
        tz = pytz.timezone('Asia/Shanghai')
        t = datetime.datetime.fromtimestamp(time_second / 1000, tz).strftime('%Y-%m-%d %H:%M:%S')
        return t

    @staticmethod
    def current_milli_time():
        milli_time = lambda: int(round(time.time() * 1000))
        return milli_time()

    def start_requests(self):
        # 默认的dict无序，遍历时不能保证安装插入顺序获取
        param_list = OrderedDict()

        # 初始赋值
        param_list['pageindex'] = 1
        param_list['pagesize'] = 300
        param_list['orderby'] = 'dim_date'
        param_list['order'] = 'desc'
        param_list['jsonp_callback'] = 'var%20{}=(x)'.format(self.generate_random_prefix())
        param_list['market'] = '(0,1,2,3)'
        param_list['rt'] = self.current_milli_time()

        # 组织查询参数
        query_param = ''
        for kv in param_list.items():
            if kv[0] is 'pageindex':
                query_param += '?{0}={1}'.format(*kv)
            else:
                query_param += '&{0}={1}'.format(*kv)

        begin_url = self.start_urls[0] + query_param
        logger.info('begin_url=%s', begin_url)

        yield Request(
            url=begin_url,
            meta={'page_no': param_list['pageindex'], 'page_size': param_list['pagesize']}
        )

    def parse(self, response):
        assert isinstance(response, Response)
        # 去除头部的'=', 得到json格式的文本
        body_list = re.split('^[^=]*(?=)=', str(response.body))
        json_text = body_list[1]

        json_obj = demjson.decode(json_text)
        assert isinstance(json_obj, dict)

        page_data = json_obj['data']
        assert isinstance(page_data, list)
        for unit in page_data:
            assert isinstance(unit, dict)

            item = ShareBuybackItem()
            item['symbol'] = unit['dim_scode']
            item['name'] = unit['securityshortname']
            item['new_price'] = unit['newprice']

            item['buyback_price_range_left'] = unit['repurpricelower']
            item['buyback_price_range_right'] = unit['repurpricecap']

            item['close_price'] = unit['cprice']
            item['buyback_volumn_range_left'] = unit['repurnumlower']
            item['buyback_volumn_range_right'] = unit['repurnumcap']

            item['share_ratio_left'] = unit['ltszxx']
            item['share_ratio_right'] = unit['ltszsx']

            item['equity_ratio_left'] = unit['zszxx']
            item['equity_ratio_right'] = unit['zszsx']

            item['buyback_amount_range_left'] = unit['repuramountlower']
            item['buyback_amount_range_right'] = unit['repuramountlimit']

            item['impl_progress'] = unit['repurprogress']

            # 获取到的是UTC时间，这里将UTC时间转换成字符串时间
            if unit['repurstartdate'] is None:
                l_start_date = 0
            else:
                l_start_date = string.atoi(str(unit['repurstartdate']))

            if unit['dim_tradedate'] is None:
                l_dim_date = 0
            else:
                l_dim_date = string.atoi(str(unit['dim_tradedate']))

            # 获取UTC时间转换后的时间戳
            item['begin_date'] = self.transfrom_beijing_time(l_start_date)
            item['announcement_date'] = self.transfrom_beijing_time(l_dim_date)

            yield item

        page_total = json_obj['pages']
        page_size = response.meta['page_size']
        page_no = response.meta['page_no']
        logger.info('page_total=%s, page_no=%s, page_size=%s', page_total, page_no, page_size)

        if page_no < page_total:
            page_no += 1
            next_url = re.sub('pageindex=\d+', 'pageindex={}'.format(page_no), response.url)
            logger.info('next_url=%s', next_url)
            yield Request(
                url=next_url,
                meta={'page_no': page_no, 'page_size': page_size}
            )