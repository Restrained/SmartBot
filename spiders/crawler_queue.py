import asyncio
import re

import redis
import json
from typing import Optional, Union

from datetime import datetime
from loguru import logger
from bricks import Request
# from bricks.downloader.playwright_ import Downloader
from bricks.downloader.go_requests import Downloader
from bricks.utils.fake import user_agent

from db.mongo import MongoClientSingleton
from scheduler import REDIS_HOST, REDIS_PORT, REDIS_DB
from utils.chrome_tls_profiles import get_random_chrome_tls_config


class Crawler:
    def __init__(self, redis_host: str = REDIS_HOST, redis_port: int = REDIS_PORT, redis_db: int = REDIS_DB):
        self.redis = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        self.proxy_set = "proxy_pool"  # 假设这是存储代理的 Redis 集合
        self.tls_config = get_random_chrome_tls_config()
        self.downloader = Downloader(tls_config=self.tls_config)  # 使用 Downloader
        self.loop = asyncio.get_event_loop()
        self.proxy_set = "proxy_set"

        # ✅ 初始化 MongoDB
        self.mongo = MongoClientSingleton(db_name="ctrip")

    @staticmethod
    async def extract_json_from_html(html_text):
        """
        从HTML中提取JSON字符串
        """
        # 使用正则表达式匹配<pre>标签中的JSON内容
        pattern = r'<pre>({.*?})</pre>'
        match = re.search(pattern, html_text, re.DOTALL)

        if match:
            json_str = match.group(1)
            try:
                # 尝试解析JSON
                json_data = json.loads(json_str)
                return json_data
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {e}")
                return None
        else:
            print("未找到JSON数据")
            return None



    async def hotel_info_spider(self, task: dict):
        """
        用于获取酒店基础信息，包括hotel_id、country等
        :param task:
        :return:
        """
        hotel_info = {}
        hotel_name = task["hotel_name"]
        body = {
            "action": "online",
            "source": "globalonline",
            "keyword": hotel_name
        }
        api = "https://m.ctrip.com/restapi/soa2/30668/search"
        method = "POST"
        headers = {
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://hotels.ctrip.com',
            'priority': 'u=1, i',
            'referer': 'https://hotels.ctrip.com/',
            'sec-ch-ua': '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': user_agent.mobile(),
        }
        response = await self.send_request(url=api, method=method, headers=headers, body=body)
        try:
            # json_content = await self.extract_json_from_html(response.text)
            # data_dict = json_content["data"][0]
            data_dict = response.json()["data"][0]
            print(data_dict)
            # hotel_name = task["hotel_name"]
            # if hotel_name == data_dict["word"]:
            hotel_info = {
                "city_id": data_dict["cityId"],
                "hotel_id": data_dict["id"],
                "city_name": data_dict["cityName"],
            }

            await asyncio.sleep(2)
        except:
            logger.warning("获取city_id的数据结构异常")
            return []
        return hotel_info


    def save_to_mongo(self, collection_name: str, data: dict):
        """
        同步方式写入 MongoDB
        """

        now = datetime.now()
        data["date"] = now.strftime("%Y-%m-%d")  # 当天日期
        data["created_at"] = now.strftime("%Y-%m-%d %H:%M:%S")  # 完整时间字符串

        self.mongo.update(collection_name, data, query={"date": data["date"], "hotel_name": data["hotel_name"], "check_in": data["check_in"], "check_out": data["check_out"] }, upsert=True)


    async def list_spider(self, task: dict):
        """
        用于爬取酒店列表页信息
        :return:
        """
        check_in = task["check_in"].replace("-", "")
        check_out = task["check_out"].replace("-", "")
        hotel_name = task["hotel_name"]
        cookie = task["cookie"]
        hotel_info = await self.hotel_info_spider(task)


        url = "https://m.ctrip.com/restapi/soa2/31454/fetchHotelInfoList"
        params = {
            "_fxpcqlniredt": "09031114110700794867",
            "x-traceID": "09031114110700794867-1762823634359-5196148"
        }
        method = "POST"
        body = {
            "head": {
                "cid": "09031114110700794867",
                "ctok": "",
                "cver": "999999",
                "lang": "01",
                "sid": "1693366",
                "syscode": "09",
                "auth": "",
                "xsid": "",
                "extension": [],
                "Locale": "zh-CN",
                "Language": "zhcn",
                "Currency": "CNY",
                "ClientID": "09031114110700794867",
                "platform": "H5",
                "aid": "66672",
                "ouid": "",
                "vid": "1762407890488.8edfuMqKRbty",
                "guid": "",
                "locale": "zh-CN",
                "pageId": "",
                "currency": "CNY",
                "timezone": "8",
                "isSSR": False,
                "group": "ctrip",
                "bu": "HBU"
            },
            "searchInfo": {
                "destinationInfo": {
                    "cityId": hotel_info['city_id'],
                    "countryId": 1,
                    "provinceId": 0,
                    "districtId": 0,
                    "destinationType": 1,
                    "fromMyLocation": False,
                    "destinationName": hotel_info['city_name'],
                    "districtName": "",
                    "provinceName": "",
                    "cityName": hotel_info['city_name'],
                    "countryName": "中国"
                },
                "checkInfo": {
                    "dateType": 0,
                    "checkInDate": check_in,
                    "checkOutDate": check_out,
                    "flexibleSearch": {},
                    "isTodayBeforeDawn": False
                },
                "roomQuantity": 1,
                "queryFilter": [
                    {
                        "data": {
                            "filterID": f"31|{hotel_info['hotel_id']}",
                            "title": hotel_name,
                            "type": "31",
                            "value": str(hotel_info['hotel_id']),
                            "subType": "",
                            "scenarioType": "",
                            "isRoomFilter": False
                        },
                        "operation": {
                            "isRoomFilter": False,
                            "otherMutexIds": [],
                            "selfMutexIds": []
                        }
                    },
                    {
                        "data": {
                            "title": "欢迎度排序",
                            "value": "1",
                            "filterID": "17|1",
                            "type": "17",
                            "subType": "2",
                            "childValue": "",
                            "sceneBitMap": 0
                        },
                        "operation": {
                            "isRoomFilter": False,
                            "isLocalFilter": False,
                            "mode": 1,
                            "otherMutexIds": [],
                            "selfMutexIds": [
                                "2439",
                                "2441"
                            ],
                            "canParentSelected": False
                        },
                        "extra": {
                            "subTitle": "",
                            "hasChild": False,
                            "nodeType": 0,
                            "extraInfo": "",
                            "isRetractStyle": False,
                            "compensateFlag": False,
                            "allTitle": [],
                            "imageList": []
                        },
                        "subItems": []
                    },
                    {
                        "data": {
                            "filterID": "80|0",
                            "title": "不含税价",
                            "value": "0",
                            "type": "80",
                            "subType": "2",
                            "sceneBitMap": 0
                        },
                        "extra": {
                            "scenarios": [
                                "4"
                            ]
                        },
                        "operation": {
                            "isLocalFilter": True,
                            "isRoomFilter": True,
                            "mode": 1
                        }
                    },
                    {
                        "data": {
                            "title": "1成人,0儿童",
                            "filterID": "29|1",
                            "type": "29",
                            "value": "1|1",
                            "subType": "2"
                        },
                        "operation": {
                            "isRoomFilter": True
                        }
                    }
                ],
                "userCoordinateInfo": {
                    "coordinateType": 3,
                    "latitude": "",
                    "longitude": ""
                },
                "residenceCode": "CN"
            },
            "sceneInfo": {
                "hotelIdListInfo": {
                    "searchHotelList": []
                },
                "intelligentSearchInfo": {
                    "isSemanticSearch": False
                },
                "bannerExtraData": {
                    "cityName": hotel_info['city_name']
                },
                "hotelAreaRecommendInfo": {
                    "queryId": 0,
                    "isShow": True
                },
                "relatedInfo": {
                    "isPreloaded": False
                }
            },
            "pagingInfo": {
                "pageIndex": 1,
                "pageSize": 10
            }
        }
        headers = {
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'content-type': 'application/json',
            'cookieorigin': 'https://m.ctrip.com',
            'currency': 'CNY',
            'locale': 'zh-CN',
            'origin': 'https://m.ctrip.com',
            'priority': 'u=1, i',
            'referer': 'https://m.ctrip.com/webapp/hotels/hotelsearch/listPage?d-country=1&d-city=7553&d-type=MAINLAND&d-name=%5B%22%E9%82%9B%E5%B4%83%22%2C%22%22%2C%22%22%2C%22%E4%B8%AD%E5%9B%BD%22%2C%22%E9%82%9B%E5%B4%83%22%5D&c-in=2025-11-11&c-out=2025-11-12&c-rooms=1&s-filters=%5B%5B%221%E6%88%90%E4%BA%BA%2C0%E5%84%BF%E7%AB%A5%22%2C%2229%7C1%22%2C%2229%22%2C%221%7C1%22%2C%22%22%2C%222%22%2C%22%22%2C%22%22%2C%22%22%2C%22%22%2C%22%22%2Cnull%5D%2C%5B%22%E9%82%9B%E5%B4%83%E5%8D%81%E6%96%B9%E5%A0%82%E9%85%92%E5%BA%97%22%2C%2231%7C5951604%22%2C%2231%22%2C%225951604%22%2C%22%22%2C%22%22%2C%22%22%2C0%2C%22%5B%5D%22%2C%22%5B%5D%22%2C%2230.398918%7C103.452489%7C1%22%2C%22KeywordSearch%22%5D%5D&locale=zh-CN&allianceid=66672&sid=1693366&curr=CNY&source-tag=10650146790&extra=%5B%7B%22isVoiceSearch%22%3A%220%22%7D%2C%7B%7D%2C%7B%22isSemanticSearch%22%3A%220%22%7D%2C%7B%22250728_HTL_HotpoiXJK%22%3A%22%22%7D%2C%7B%22searchType%22%3A%22search_page%22%7D%5D&s-keyword=%5B%22%E9%82%9B%E5%B4%83%E5%8D%81%E6%96%B9%E5%A0%82%E9%85%92%E5%BA%97%22%2C%2231%7C5951604%22%2C%2231%22%2C%225951604%22%2C%22%22%2C%22%22%2C%22%22%2C0%2C%22%5B%5D%22%2C%22%5B%5D%22%2C%2230.398918%7C103.452489%7C1%22%5D&page-token=a1be182a-3390-4422-9b96-b7858485ad00&dplinktracelogid=a4317a9a43aa949e474ae8eb98306dc0&keywordsource=searchrecomdclick&destinationsource=searchrecomdclick&userActionTrace=%7B%22associationToken%22%3A%22keyword_5951604%22%2C%22associationTraceId%22%3A%22100025527-0a918b8e-489658-1807700%22%2C%22destinationId%22%3A%22%22%2C%22destinationType%22%3A%22%22%2C%22keywordType%22%3A%221%22%2C%22keywordId%22%3A%225951604%22%2C%22keywordSource%22%3A%22searchrecomdclick%22%2C%22frompage%22%3A%22keyword%22%2C%22sourcePage%22%3A%22inquire%22%2C%22sourceType%22%3A%22keyword%22%2C%22channeltype%22%3A%22h5%22%7D',
            'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': user_agent.mobile(),
            'x-ctx-country': 'CN',
            'x-ctx-currency': 'CNY',
            'x-ctx-locale': 'zh-CN',
            'x-ctx-ubt-pageid': '212093',
            'x-ctx-ubt-pvid': '4',
            'x-ctx-ubt-sid': '15',
            'x-ctx-ubt-vid': '1762407890488.8edfuMqKRbty',
            'x-ctx-wclient-req': 'bee9a7e8cb500f425acf6ae00a2c7938',
            'Cookie': cookie
        }
        response = await self.send_request(url=url, method=method, headers=headers, body=body, params=params)
        # json_data = await self.extract_json_from_html(response.text)
        logger.info("列表页数据爬取完成:", response.json())
        logger.info(response.request.curl)

        # ✅ 写入 Mongo
        save_data = {
            "city": task.get("city"),
            "hotel_name": task.get("hotel_name"),
            "check_in": task.get("check_in"),
            "check_out": task.get("check_out"),
            "task_type": "list",
            "status_code": response.status_code,
            "response": json.dumps(response.json()),
        }
        self.save_to_mongo("ctrip_list_results", save_data)


        return response.json()

    async def detail_spider(self, task: dict):
        """
        用于爬取酒店详情页信息
        :return:
        """
        check_in = task["check_in"]
        check_out = task["check_out"]
        cookie = task["cookie"]
        hotel_info = await self.hotel_info_spider(task)
        if not hotel_info:
            save_data = {
                "city": task.get("city"),
                "hotel_name": task.get("hotel_name"),
                "check_in": task.get("check_in"),
                "check_out": task.get("check_out"),
                "task_type": "detail",
                "status_code": 404,
                "response": json.dumps({"msg": "搜索不到酒店"}),
            }
        else:
            url = "https://m.ctrip.com/restapi/soa2/33278/getHotelRoomListInland"

            method = "POST"
            body = {
                "search": {
                    "isRSC": False,
                    "isSSR": False,
                    "hotelId": hotel_info['hotel_id'],
                    "roomId": 0,
                    "checkIn": check_in.replace("-", ""),
                    "checkOut": check_out.replace("-", ""),
                    "roomQuantity": 1,
                    "adult": 1,
                    "childInfoItems": [],
                    "isIjtb": False,
                    "priceType": 2,
                    "hotelUniqueKey": "",
                    "mustShowRoomList": [],
                    "location": {
                        "geo": {
                            "cityID": 2
                        }
                    },
                    "filters": [
                        {
                            "filterId": "17|1",
                            "type": "17",
                            "value": "1",
                            "title": ""
                        }
                    ],
                    "meta": {
                        "fgt": -1,
                        "roomkey": "",
                        "minCurr": "",
                        "minPrice": "",
                        "roomToken": ""
                    },
                    "hasAidInUrl": False,
                    "cancelPolicyType": 0,
                    "fixSubhotel": 0,
                    "isFirstEnterDetailPage": "T",
                    "listTraceId": "100053755-0a9504c5-489411-84496",
                    "abResultEntities": [
                        {
                            "key": "221221_IBU_ormlp",
                            "value": "A"
                        },
                        {
                            "key": "230815_IBU_pcpto",
                            "value": "B"
                        },
                        {
                            "key": "240530_IBU_Opdp",
                            "value": "B"
                        },
                        {
                            "key": "251015_HTL_brkfstCOL",
                            "value": "B"
                        }
                    ],
                    "extras": {
                        "loginAB": "",
                        "exposeBedInfos": "",
                        "enableChildAgeGroup": "T",
                        "needEntireSetRoomDesc": ""
                    }
                },
                "head": {
                    "platform": "PC",
                    "cver": "0",
                    "cid": "1752572855451.d0d8IHkO2nX9",
                    "bu": "HBU",
                    "group": "ctrip",
                    "aid": "",
                    "sid": "",
                    "ouid": "",
                    "locale": "zh-CN",
                    "timezone": "8",
                    "currency": "CNY",
                    "pageId": "10650171194",
                    "vid": "1752572855451.d0d8IHkO2nX9",
                    "guid": "",
                    "isSSR": False,
                    "extension": [
                        {
                            "name": "cityId",
                            "value": ""
                        },
                        {
                            "name": "checkIn",
                            "value": check_in
                        },
                        {
                            "name": "checkOut",
                            "value": check_out
                        }
                    ]
                }
            }


            headers = {
                        'accept': 'application/json',
                        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
                        'content-type': 'application/json',
                        'cookieorigin': 'https://hotels.ctrip.com',
                        'origin': 'https://hotels.ctrip.com',
                        'phantom-token': '1004-common-Gg4RDE8gIMZEM7WGdvHGv01RToYnMy9cjL8wUNIF1ifQiFzj9zYmgY3QjLPygfw3QvzAEamiNLJXSvoFw4HR9oxthyPAvO4EX7ihPwD4eHUvqmRkLydYbBY5SRMmvhMR35yPUwGQYDFE0NifGyqciAgwnSWS5RdqigdYZLEBj7hEpYOE5SyZ1iS5KP5jFTjaOEboy0ELnilZYzEcoYpHyZEAQYZAyb8KTcimbjdSjlUWkNyM1I3BwphjamwcBeBAE9SIdZwsDilZR4E6TYOcyHAK6hio5j1tjkcWZDy6EXQY3DyMhR79YlPWDgvM9WX9wU3ytzIkLKa0j7kR48WHEO9ilayH4w3FeXbj5hItBe45yoEkmigSJdHilfjf9E7BySE3UYB0iNGwdkjPhR7zYDSwAnjbgvFEQDiBsJF5K9GKo6KnQYXhKU8E9zYbdKMmeafyl0YnHWblyGSjUMKtAK64WQY3px4PRFOvTzRNDyLTw9DRZtvTGyapWtqJ40WTnY6cv3fEtlRNBITpjfoy8qRHpjQ8JXdYToIN1j0zrglKX8wnlRS8IggxA7KSYLZyUOvbhIk7jLqR73JbtEnswDzi9QyZTwQse5UWZSj7gy7cwlfeGXE13JnhyLAvHce7nEPlyDsE1GvLTebMJqnRqojtGi7mEOaEq8wFNWkmWcdWX1YgoEOJ0ZWz6i3YBzvPSRz6IgGwTfyL4YMAwh0jLTwSbYnGwbEsNibmI3YBMWoOwo3rNlYHsE48yN3WgSEXY6zxDaR33xFMvcpe3ZYB3iN9YgmRU8w5aRqY67w7qyphE9BeOQEg6jAtWbPvtzYafyHYX6YApJpsILHrlnK70esnEFNWGPElseN5IsYgcrsqekPEghYZFWBgE7Pj3de3gRDcRPMJnGY34rs3JNymYQQxhaesFypQY5qWN8EfHjnge8pRo1RqGWNhE4yt9J85WQY45y7DYPbjnpiLljOcvXLwFyzLIBYzBeU9EFUI9DYUkikqwUnRpPElBWaPIAPIGJdYHXWG6yp9Wz9JkZea9xUtKNYodYnTWcNETzj75wadvcGjmnefZyBMe8Y5LihDvp0Y8cYcbrGFr1BWsYsLigsrhGyb0jcGwlnvSBjlgvZvbqKHYoLWQ9WqnrOkJSOWmXe3Nw9pjcYtUWtZyktwb4jnti4miMzxfsWDnjqrAlxsmYcswMmIbrLyfBWp1jH1x9qJnLxHaYdjfDY4nYTNj5Y3pwXdKpMWALRbFWMZw1kJZtWqBRszyGqRH3RSNvZqEflRmzKtG',
                        'priority': 'u=1, i',
                        'referer': 'https://hotels.ctrip.com/',
                        'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
                        'sec-ch-ua-mobile': '?0',
                        'sec-ch-ua-platform': '"Windows"',
                        'sec-fetch-dest': 'empty',
                        'sec-fetch-mode': 'cors',
                        'sec-fetch-site': 'same-site',
                        'user-agent': user_agent.mobile(),
                        "Cookie": cookie
                    }
            response = await self.send_request(url=url, method=method, headers=headers, body=body)
            logger.info("详情页价格数据爬取完成:", response.json())
            logger.info(response.request.curl)


            # ✅ 写入 Mongo
            save_data = {
                "city": task.get("city"),
                "hotel_name": task.get("hotel_name"),
                "check_in": task.get("check_in"),
                "check_out": task.get("check_out"),
                "task_type": "detail",
                "status_code": response.status_code,
                "response": json.dumps(response.json()),
            }
        self.save_to_mongo("ctrip_detail_results", save_data)
        return True

    async def get_proxy(self):

        while True:
            proxy_set = self.redis.smembers(self.proxy_set)
            if proxy_set:
                break
            logger.warning("代理池为空，等待投放")
            await asyncio.sleep(5)
        return "http://" + list(proxy_set)[0]

    async def send_request(self, url: str, method: str = "GET", params: dict = None,
                           body: Optional[Union[str, dict]] = None, headers: dict = None, proxy: str = None):
        """
        用于定义实际发起请求的配置
        :return:
        """

        while True:
            proxies = await self.get_proxy()  # 获取代理
            request = Request(url=url, method=method, headers=headers, params=params, body=body, timeout=20,
                              proxies=proxies
                              )
            response = self.downloader.fetch(request)  # 使用 Downloader
            if response.status_code == 200:
                break
            elif response.status_code == -1 and response.error == "ProxyError":

                logger.info("代理失效，等待切换")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.redis.srem, self.proxy_set,
                                           proxies.replace("http://", ''))  # 异步调用同步方法
                await asyncio.sleep(2)
            elif response.error == "ConnectionError":
                logger.warning(f"连接错误，继续重试")
                await asyncio.sleep(2)
            else:
                logger.info(response.request.curl)
                logger.warning(f"存在未知错误，长时间休眠等待，返回码{response.status_code}, 具体响应内容{response.text}")
                await asyncio.sleep(3600)  # 非阻塞方式休眠 1 小时，允许事件循环继续执行其他任务
                # todo: 这里可以添加消息通知机制

        return response

    async def listen_queues(self):
        """
        监听两个队列，处理任务
        :return:
        """
        while True:
            list_task = self.redis.spop('ctrip_list_queue')
            if list_task:
                print("从list队列获取任务")
                task = json.loads(list_task)
                await self.list_spider(task)

            detail_task = self.redis.spop('ctrip_detail_queue')
            if detail_task:
                print("从detail队列获取任务")
                task = json.loads(detail_task)
                await self.detail_spider(task)

            # 休眠一段时间再去监听队列
            await asyncio.sleep(1)


if __name__ == '__main__':
    crawler = Crawler()
    # print(asyncio.run(crawler.detail_spider({
    #     "city": "邛崃",
    #     "hotel_name": "邛崃十方堂酒店",
    #     "check_in": "2025-11-11",
    #     "check_out": "2025-11-12",
    #     "cookie": "suid=ABfzl/ARubueEgOPkeYpog==; GUID=09031056210400513746; nfes_isSupportWebP=1; UBT_VID=1762506623797.9e8a4yWxabTK; nfes_isSupportWebP=1; suid=ABfzl/ARubueEgOPkeYpog==; _RGUID=3fdb1fac-9e4e-4aa9-857f-697df63a6eb5; _resDomain=https%3A%2F%2Fws-s.tripcdn.cn; _pd=%7B%22_o%22%3A1%2C%22s%22%3A5%2C%22_s%22%3A0%7D; cticket=275970CA0D9645CDAE0CE9E8F4FF3237AA6522C424AA85F53BA14D1AE6A74B5A; login_type=0; login_uid=1F4214526D417B3AF66183538749BB47; DUID=u=C6A85CADBAD8C1865A04E22AB1B4ED03&v=0; IsNonUser=F; AHeadUserInfo=VipGrade=0&VipGradeName=%C6%D5%CD%A8%BB%E1%D4%B1&UserName=&NoReadMessageCount=0; _udl=708D70C2B179E2F91CC5ED1C2CCE362D; _lizard_LZ=XzVFUBOTeNZPo7CbycrdJDnY58wAqWuR1tmHEflIkLKs0jS3QGMx-ih+694vpg2a; _bfa=1.1762506623797.9e8a4yWxabTK.1.1762506626653.1762506703429.1.3.10650096342"
    # })))
    asyncio.run(crawler.listen_queues())
