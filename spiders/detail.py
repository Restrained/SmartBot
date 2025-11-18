import random
import time

import loguru
from bricks import const
from bricks.core import signals
from bricks.core.signals import Failure, Success
from bricks.db.redis_ import Redis
from bricks.downloader import go_requests
from bricks.lib.queues import RedisQueue

from bricks.plugins.storage import to_mongo
from bricks.spider import template
from bricks.spider.template import Config, Context
from bricks.utils.fake import user_agent

from db.mongo import MongoClientSingleton


class Detail(template.Spider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.queue_name="ctrip_hotel_detail"
        self.redis = Redis()
        self.mongo = MongoClientSingleton(
            db_name="ctrip"
        )

    @property
    def config(self) -> Config:
        return Config(
            init=[
                template.Init(
                    func=self.init_seeds,

                ),
            ],
            download=[
                template.Download(
                    url="https://m.ctrip.com/restapi/soa2/33278/getHotelRoomListInland",
                    method="POST",
                    body={"search":{"isRSC":False,"isSSR":False,"hotelId":"","roomId":0,"checkIn":"20251106","checkOut":"20251107","roomQuantity":1,"adult":2,"childInfoItems":[],"isIjtb":False,"priceType":2,"hotelUniqueKey":"","mustShowRoomList":[],"location":{"geo":{"cityID":0}},"filters":[],"meta":{"fgt":-1,"roomkey":"","minCurr":"","minPrice":"","roomToken":""},"hasAidInUrl":False,"cancelPolicyType":0,"fixSubhotel":0,"listTraceId":"","abResultEntities":[{"key":"221221_IBU_ormlp","value":"A"},{"key":"230815_IBU_pcpto","value":"B"},{"key":"240530_IBU_Opdp","value":"B"}],"extras":{"loginAB":"","exposeBedInfos":"","enableChildAgeGroup":"T","needEntireSetRoomDesc":"","closeOnlineRoomListOptimize":False}},"head":{"platform":"PC","cver":"0","cid":"1761970502941.ed185PjtzJ6O","bu":"HBU","group":"ctrip","aid":"4897","sid":"130026","ouid":"","locale":"zh-CN","timezone":"8","currency":"CNY","pageId":"10650171194","vid":"1761970502941.ed185PjtzJ6O","guid":"","isSSR":False,"extension":[{"name":"cityId","value":""},{"name":"checkIn","value":""},{"name":"checkOut","value":""}]}},
                    timeout=10,
                    headers={
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
                        "Cookie": "{cookie}"
                        # "Cookie": "Hm_lvt_a8d6737197d542432f4ff4abc6e06384=1762417592; HMACCOUNT=B610EFBE5F17A585; UBT_VID=1762417592384.eed89694NvJc; GUID=09031178110277323443; _ga=GA1.1.370384083.1762417593; _RGUID=537c5fbc-9360-4578-8756-06b4e8a05779; nfes_isSupportWebP=1; Session=smartlinkcode=U59318281&smartlinklanguage=zh&SmartLinkKeyWord=&SmartLinkQuary=&SmartLinkHost=; Union=AllianceID=66672&SID=59318281&OUID=&createtime=1762417594&Expires=1763022394484; login_type=0; IsNonUser=F; AHeadUserInfo=VipGrade=0&VipGradeName=%C6%D5%CD%A8%BB%E1%D4%B1&UserName=&NoReadMessageCount=0; _udl=708D70C2B179E2F91CC5ED1C2CCE362D; Hm_lpvt_a8d6737197d542432f4ff4abc6e06384=1762419499; MKT_Pagesource=PC; ibulocale=zh_cn; cookiePricesDisplayed=CNY; _abtest_userid=198c8944-582f-4b9d-987c-7505515d037c; MKT_CKID=1762419544397.03xyg.zp55; IBU_showtotalamt=2; _ga_5DVRDQD429=GS2.1.s1762477700$o3$g0$t1762477700$j60$l0$h1933400632; _ga_B77BES1Z8Z=GS2.1.s1762477700$o3$g0$t1762477700$j60$l0$h0; _ga_9BZF483VNQ=GS2.1.s1762477700$o3$g0$t1762477700$j60$l0$h0; cticket=ACF57423D6041FB54018F0855E01AD1085F96C5A79811924322A956ECFAF47A7; login_uid=7D1A5314A6EFC81A98071C692B9B7315; DUID=u=FEBCC741BA334F1730431DA7152E6215&v=0; ibulanguage=ZH-CN; _jzqco=%7C%7C%7C%7C1762419544763%7C1.894984386.1762419544395.1762477703231.1762477868226.1762477703231.1762477868226.0.0.0.6.6; _bfa=1.1762417592384.eed89694NvJc.1.1762477703063.1762477868099.3.3.10650171194",
                        # 'Cookie': 'Hm_lvt_a8d6737197d542432f4ff4abc6e06384=1762442057; HMACCOUNT=24A09E9879A93AE2; UBT_VID=1762442057626.ae0akhU7blb6; GUID=09031091310313246007; _ga=GA1.1.911758281.1762442058; _RGUID=207ba222-e9a3-4bf6-a972-5e0fcb646c3f; nfes_isSupportWebP=1; Session=smartlinkcode=U59318281&smartlinklanguage=zh&SmartLinkKeyWord=&SmartLinkQuary=&SmartLinkHost=; Union=AllianceID=66672&SID=59318281&OUID=&createtime=1762442060&Expires=1763046859626; cticket=DCF631E07514CEAF393D2C82E35907512B01161951E04403655BD720D94176B3; login_type=0; login_uid=BD61C72957876749CE8A2267387473EC; DUID=u=45D474F4A9918C7527831998A45BC08C&v=0; IsNonUser=F; AHeadUserInfo=VipGrade=0&VipGradeName=%C6%D5%CD%A8%BB%E1%D4%B1&UserName=&NoReadMessageCount=0; _udl=708D70C2B179E2F91CC5ED1C2CCE362D; Hm_lpvt_a8d6737197d542432f4ff4abc6e06384=1762442188; _ga_9BZF483VNQ=GS2.1.s1762442058$o1$g1$t1762442189$j48$l0$h0; _ga_5DVRDQD429=GS2.1.s1762442058$o1$g1$t1762442189$j48$l0$h416756687; _ga_B77BES1Z8Z=GS2.1.s1762442058$o1$g1$t1762442189$j48$l0$h0; MKT_Pagesource=PC; ibulocale=zh_cn; cookiePricesDisplayed=CNY; _abtest_userid=ed7b62dd-21ec-433d-98da-618141897a2a; MKT_CKID=1762442199240.wlz2z.r4q9; IBU_showtotalamt=2; ibulanguage=ZH-CN; _jzqco=%7C%7C%7C%7C1762442199389%7C1.818043013.1762442199238.1762442199238.1762442208492.1762442199238.1762442208492.0.0.0.2.2; _bfa=1.1762442057626.ae0akhU7blb6.1.1762442200522.1762442208950.1.6.10650171194'
                    },
                    ok={"response.status_code == 400": signals.Pass}
                ),


            ],
            parse=[
                template.Parse(
                    func=self._parse,

                )
            ],
            pipeline=[
                template.Pipeline(
                    func=to_mongo,
                    kwargs={
                        "path": "ctrip_detail",
                        "conn": self.mongo
                    },
                    success=True
                )
            ],
            events={
                const.BEFORE_REQUEST: [
                    template.Task(
                        func=self.set_hotel_id,

                    ),

                ],
                const.AFTER_REQUEST: [
                    template.Task(
                        func=self.is_success,

                    ),

                ],

            }
        )

    def _parse(self, context: Context):
        return []

    def set_hotel_id(self, context: Context):
        seeds = context.seeds
        request = context.request
        request.body["search"]["hotelId"] = seeds["hotel_id"]



    def is_success(self, context: Context):
        response = context.response

        if "totalPriceInfo" in response.text:
            loguru.logger.info("请求成功！！！！！！！！")
            time.sleep(random.randint(61, 90))
            raise Failure
        loguru.logger.info(response.text)
        raise Success

    def init_seeds(self):
        return [
            {"hotel_id": 5951604, "cookie": "suid=8FiTdvARuLtWDnaFyyQF/w==; GUID=09031045310399864174; nfes_isSupportWebP=1; UBT_VID=1762506138312.8833dcXDdE4c; _resDomain=https%3A%2F%2Fbd-s.tripcdn.cn; nfes_isSupportWebP=1; suid=8FiTdvARuLtWDnaFyyQF/w==; _RGUID=ad871f33-bb6d-4e6f-a6ea-33bd6e573ad8; _pd=%7B%22_o%22%3A1%2C%22s%22%3A6%2C%22_s%22%3A0%7D; cticket=75177FA089C3ECAE9D7083403640093BFD5715510E07BC6E942BD3AB47047485; login_type=0; login_uid=E146B79EBD8ACAD894A5CEED030DB906; DUID=u=24A72C88CABA12C18B4938740494DB82&v=0; IsNonUser=F; AHeadUserInfo=VipGrade=0&VipGradeName=%C6%D5%CD%A8%BB%E1%D4%B1&UserName=&NoReadMessageCount=0; _udl=708D70C2B179E2F91CC5ED1C2CCE362D; _lizard_LZ=PdQeEFLJaZHOVNUGTXBfMKYCWRSAcIDbkhls7x3nvi61-0rwqpuztg98mjo24y+5; _bfa=1.1762506138312.8833dcXDdE4c.1.1762506141156.1762506205347.1.3.10650096342"},
            {"hotel_id": 109340366, "cookie": "suid=JL4BWvARv77YQjie/ezuHQ==; GUID=09031094110838502174; nfes_isSupportWebP=1; UBT_VID=1762838950330.4207775Bz3VY; _resDomain=https%3A%2F%2Fbd-s.tripcdn.cn; nfes_isSupportWebP=1; suid=JL4BWvARv77YQjie/ezuHQ==; _RGUID=79d96642-3e4d-4708-bfd3-a020f9b8b069; _pd=%7B%22_o%22%3A1%2C%22s%22%3A4%2C%22_s%22%3A0%7D; cticket=B929416F056216A128B71CAE889A0ECACF2D6ACBCA224E8A37C606B865409AD4; login_type=0; login_uid=85DC04E82C9E3C5E43625C15FD957192; DUID=u=957C6686DE2891A191FAB89275962C56&v=0; IsNonUser=F; AHeadUserInfo=VipGrade=0&VipGradeName=%C6%D5%CD%A8%BB%E1%D4%B1&UserName=&NoReadMessageCount=0; _udl=708D70C2B179E2F91CC5ED1C2CCE362D; _lizard_LZ=jkACmGBIt-YS9UMF1HdiTlR0ZKzL3qvoc6yQ7xnpsr+PuVhNwg245f8EOXJWbDae; _bfa=1.1762838950330.4207775Bz3VY.1.1762838952133.1762838969104.1.3.10650096342"},
            {"hotel_id": 89805793, "cookie": "suid=9XGja/ARv77YQjie/ezuHQ==; GUID=09031057210838542787; nfes_isSupportWebP=1; UBT_VID=1762838979930.f326hgGcPJFX; _resDomain=https%3A%2F%2Fws-s.tripcdn.cn; nfes_isSupportWebP=1; suid=9XGja/ARv77YQjie/ezuHQ==; _RGUID=49f89ef7-7d59-4d09-8440-40a1580f6ec9; _pd=%7B%22_o%22%3A2%2C%22s%22%3A4%2C%22_s%22%3A0%7D; cticket=542DEDB08C579AF0B7746428A13767B6F8690CB833B254E8EAA2F9DE31D46364; login_type=0; login_uid=5C65E6646178165BD5AACFC50C5BFEFF; DUID=u=6EBC92FF9C0758524911CFD65CCFDC52&v=0; IsNonUser=F; AHeadUserInfo=VipGrade=0&VipGradeName=%C6%D5%CD%A8%BB%E1%D4%B1&UserName=&NoReadMessageCount=0; _udl=708D70C2B179E2F91CC5ED1C2CCE362D; _lizard_LZ=iABCJDSfIYTRuMNHj4wbFZ5a9dp1moEv8e-6yKrWU2GVqhLOz0kgtsPlnQcx+7X3; _bfa=1.1762838979930.f326hgGcPJFX.1.1762838981612.1762839159845.1.3.10650096342"},
            {"hotel_id": 114935658, "cookie": "suid=wIv+AvARwL4AEh2q1z50Hg==; GUID=09031044310838932062; nfes_isSupportWebP=1; UBT_VID=1762839233859.d0a2nPPJFu2D; _resDomain=https%3A%2F%2Fbd-s.tripcdn.cn; nfes_isSupportWebP=1; suid=wIv+AvARwL4AEh2q1z50Hg==; _RGUID=863d03c9-bb32-4fa4-860f-7c9ef3c3d34e; _pd=%7B%22_o%22%3A1%2C%22s%22%3A3%2C%22_s%22%3A0%7D; cticket=FE8790FE987293191CD7452DAF999AC1F0C89ADC915BA734D13D3AD1E7D219CE; login_type=0; login_uid=CBC4AD88F025013B8CABF540C14A9DE4; DUID=u=BC4FB2E05E4A60C1D2A6A96686E2A35B&v=0; IsNonUser=F; AHeadUserInfo=VipGrade=0&VipGradeName=%C6%D5%CD%A8%BB%E1%D4%B1&UserName=&NoReadMessageCount=0; _udl=708D70C2B179E2F91CC5ED1C2CCE362D; _lizard_LZ=xMFPdEKUQVGYXzITma+u4RcH-roL6wl2DC10gveqtJZpfShj5y9ONnW3iBsk7bA8; _bfa=1.1762839233859.d0a2nPPJFu2D.1.1762839235538.1762839389440.1.3.10650096342"},
            {"hotel_id": 47993522, "cookie": "suid=EiJCSPARv77LNrOpOsqH/g==; GUID=09031074410838459866; nfes_isSupportWebP=1; UBT_VID=1762838920515.185eqZpuHzw6; _resDomain=https%3A%2F%2Fbd-s.tripcdn.cn; nfes_isSupportWebP=1; suid=EiJCSPARv77LNrOpOsqH/g==; _RGUID=0c3f15b2-9dfd-4b43-a209-1249f948b43d; _pd=%7B%22_o%22%3A0%2C%22s%22%3A3%2C%22_s%22%3A0%7D; cticket=625EFADFC10FB2B9B2AE636FF4591AB335D972A394B3D408D24CDB1592A3B2C2; login_type=0; login_uid=41653F6736085132BA41E07DCA2877EB; DUID=u=F7FF697B08DD1C988710A83707C6657C&v=0; IsNonUser=F; AHeadUserInfo=VipGrade=0&VipGradeName=%C6%D5%CD%A8%BB%E1%D4%B1&UserName=&NoReadMessageCount=0; _udl=708D70C2B179E2F91CC5ED1C2CCE362D; _lizard_LZ=dtDCLRTaUeYXFQPAVb1Ikxyco84iprKNZlhn7GBg2jfzHmO3MJEquw+9S-v0W6s5; _bfa=1.1762838920515.185eqZpuHzw6.1.1762838922276.1762838939341.1.3.10650096342"},
        ]


if __name__ == "__main__":
    proxy = {
        'ref': "bricks.lib.proxies.RedisProxy",
        'key': 'proxy_set',

    }
    spider = Detail(
        concurrency=5,
        **{"init.queue.size": 1000000},
        task_queue=RedisQueue(),
        downloader=go_requests.Downloader(),
        proxy=proxy

    )

    spider.run(task_name='all')
#     spider.survey({
#         "hotel_id": 1209067
# })
