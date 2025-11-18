import asyncio
import aiohttp
from urllib.parse import urlencode

import redis
import json
from typing import Optional, Union

from datetime import datetime

from loguru import logger
from bricks import Request
from bricks.downloader.go_requests import Downloader
from bricks.utils.fake import user_agent

from db.mongo import MongoClientSingleton
from scheduler import REDIS_HOST, REDIS_PORT, REDIS_DB


class CrawlerByAuto:
    def __init__(self, redis_host: str = REDIS_HOST, redis_port: int = REDIS_PORT, redis_db: int = REDIS_DB):
        self.redis = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        self.downloader = Downloader()  # 使用 Downloader
        self.loop = asyncio.get_event_loop()
        self.proxy_set = "proxy_set"
        self.url = "http://127.0.0.1:8004"

        # ✅ 初始化 MongoDB
        self.mongo = MongoClientSingleton(db_name="ctrip")

        self.session = None

        # 缓冲队列：存储正在处理的任务，避免重复执行
        self.processing_list_tasks = set()  # 正在处理的列表任务标识
        self.processing_detail_tasks = set()  # 正在处理的详情任务标识

    def _get_task_identifier(self, task: dict, task_type: str) -> str:
        """生成任务唯一标识符"""
        if task_type == "list":
            return f"list_{task['hotel_name']}_{task['check_in']}_{task['check_out']}"
        elif task_type == "detail":
            return f"detail_{task['hotel_name']}_{task['check_in']}_{task['check_out']}"
        else:
            return f"unknown_{hash(json.dumps(task, sort_keys=True))}"

    async def get_session(self):
        """获取或创建 aiohttp session"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=240)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def hotel_info_spider(self, task: dict):
        """
        用于获取酒店基础信息，包括hotel_id、country等
        :param task:
        :return:
        """
        keyword = task["hotel_name"]
        body = {
            "action": "online",
            "source": "globalonline",
            "keyword": keyword
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
                "hotel_id": str(data_dict["id"]),
                "keyword": keyword,
                "check_in": task["check_in"].replace("-", ""),
                "check_out": task["check_out"].replace("-", ""),
                "city_id": str(data_dict["cityId"]),
                "city_name": data_dict["cityName"],
                "province_name": data_dict.get("districtName", "")
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

        self.mongo.update(collection_name, data,
                          query={"date": data["date"], "hotel_name": data["hotel_name"], "check_in": data["check_in"],
                                 "check_out": data["check_out"]}, upsert=True)

    async def list_spider(self, task: dict):
        """
        用于爬取酒店列表页信息
        :return:
        """
        task_id = self._get_task_identifier(task, "list")

        try:
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

        except Exception as e:
            logger.error(f"列表页爬取失败: {e}")
            # 记录失败状态到 MongoDB
            save_data = {
                "city": task.get("city"),
                "hotel_name": task.get("hotel_name"),
                "check_in": task.get("check_in"),
                "check_out": task.get("check_out"),
                "task_type": "list",
                "status_code": 500,
                "response": json.dumps({"error": str(e)}),
            }
            self.save_to_mongo("ctrip_list_results", save_data)
            return None

        finally:
            # 无论成功还是失败，都从缓冲队列中移除
            if task_id in self.processing_list_tasks:
                self.processing_list_tasks.remove(task_id)
                logger.info(f"列表任务 {task_id} 已从缓冲队列移除")

    async def detail_spider(self, task: dict):
        """
        使用 aiohttp 的异步详情爬虫
        """
        task_id = self._get_task_identifier(task, "detail")

        try:
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
                hotel_info["fetch_detail"] = "true"
                base_url = "http://127.0.0.1:8004/xc/getHotelRoomListInland"
                query_string = urlencode(hotel_info)
                url = f"{base_url}?{query_string}"

                headers = {
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
                    'Referer': 'http://127.0.0.1:8004/docs',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
                    'accept': 'application/json',
                }

                session = await self.get_session()
                try:
                    async with session.get(url, headers=headers) as response:
                        response_data = await response.json()
                        logger.info("详情页价格数据爬取完成:", response_data)

                        save_data = {
                            "city": task.get("city"),
                            "hotel_name": task.get("hotel_name"),
                            "check_in": task.get("check_in"),
                            "check_out": task.get("check_out"),
                            "task_type": "detail",
                            "status_code": response.status,
                            "response": json.dumps(response_data),
                        }
                except Exception as e:
                    logger.error(f"详情页请求失败: {e}")
                    save_data = {
                        "city": task.get("city"),
                        "hotel_name": task.get("hotel_name"),
                        "check_in": task.get("check_in"),
                        "check_out": task.get("check_out"),
                        "task_type": "detail",
                        "status_code": 500,
                        "response": json.dumps({"error": str(e)}),
                    }

            self.save_to_mongo("ctrip_detail_results", save_data)
            return True

        except Exception as e:
            logger.error(f"详情页爬取失败: {e}")
            # 记录失败状态到 MongoDB
            save_data = {
                "city": task.get("city"),
                "hotel_name": task.get("hotel_name"),
                "check_in": task.get("check_in"),
                "check_out": task.get("check_out"),
                "task_type": "detail",
                "status_code": 500,
                "response": json.dumps({"error": str(e)}),
            }
            self.save_to_mongo("ctrip_detail_results", save_data)
            return False

        finally:
            # 无论成功还是失败，都从缓冲队列中移除
            if task_id in self.processing_detail_tasks:
                self.processing_detail_tasks.remove(task_id)
                logger.info(f"详情任务 {task_id} 已从缓冲队列移除")

    async def close(self):
        """关闭 session"""
        if self.session:
            await self.session.close()

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
                # await asyncio.sleep(3600)  # 非阻塞方式休眠 1 小时，允许事件循环继续执行其他任务
                return {}
                # todo: 这里可以添加消息通知机制

        return response

    async def listen_queues(self):
        while True:
            # 检查列表任务队列
            list_task = self.redis.spop('ctrip_list_queue')
            if list_task:
                task = json.loads(list_task)
                task_id = self._get_task_identifier(task, "list")

                # 检查任务是否已经在处理中
                if task_id not in self.processing_list_tasks:
                    self.processing_list_tasks.add(task_id)
                    logger.info(f"从 list 队列获取任务（异步执行）: {task_id}")
                    asyncio.create_task(self.list_spider(task))
                else:
                    logger.info(f"列表任务 {task_id} 正在处理中，跳过重复执行")
                    # 如果任务正在处理，把任务放回队列稍后重试
                    # await self.redis.sadd('ctrip_list_queue', list_task)
                    await asyncio.sleep(5)  # 等待一段时间再检查

            # 检查详情任务队列
            detail_task = self.redis.spop('ctrip_detail_queue')
            if detail_task:
                task = json.loads(detail_task)
                task_id = self._get_task_identifier(task, "detail")

                # 检查任务是否已经在处理中
                if task_id not in self.processing_detail_tasks:
                    self.processing_detail_tasks.add(task_id)
                    logger.info(f"从 detail 队列获取任务（异步执行）: {task_id}")
                    asyncio.create_task(self.detail_spider(task))
                else:
                    logger.info(f"详情任务 {task_id} 正在处理中，跳过重复执行")
                    # 如果任务正在处理，把任务放回队列稍后重试
                    # await self.redis.sadd('ctrip_detail_queue', detail_task)
                    await asyncio.sleep(5)  # 等待一段时间再检查

            await asyncio.sleep(1)


if __name__ == '__main__':
    crawler = CrawlerByAuto()
    # print(asyncio.run(crawler.detail_spider({
    #     "hotel_name": "三亚西岛剑麻酒店",
    #     "check_in": "2025-11-18",
    #     "check_out": "2025-11-19",
    #     "city": "三亚",
    #
    #     # "cookie": "suid=ABfzl/ARubueEgOPkeYpog==; GUID=09031056210400513746; nfes_isSupportWebP=1; UBT_VID=1762506623797.9e8a4yWxabTK; nfes_isSupportWebP=1; suid=ABfzl/ARubueEgOPkeYpog==; _RGUID=3fdb1fac-9e4e-4aa9-857f-697df63a6eb5; _resDomain=https%3A%2F%2Fws-s.tripcdn.cn; _pd=%7B%22_o%22%3A1%2C%22s%22%3A5%2C%22_s%22%3A0%7D; cticket=275970CA0D9645CDAE0CE9E8F4FF3237AA6522C424AA85F53BA14D1AE6A74B5A; login_type=0; login_uid=1F4214526D417B3AF66183538749BB47; DUID=u=C6A85CADBAD8C1865A04E22AB1B4ED03&v=0; IsNonUser=F; AHeadUserInfo=VipGrade=0&VipGradeName=%C6%D5%CD%A8%BB%E1%D4%B1&UserName=&NoReadMessageCount=0; _udl=708D70C2B179E2F91CC5ED1C2CCE362D; _lizard_LZ=XzVFUBOTeNZPo7CbycrdJDnY58wAqWuR1tmHEflIkLKs0jS3QGMx-ih+694vpg2a; _bfa=1.1762506623797.9e8a4yWxabTK.1.1762506626653.1762506703429.1.3.10650096342"
    # })))
    asyncio.run(crawler.listen_queues())