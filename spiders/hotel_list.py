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

from db.mongo import MongoInfo


class HotelList(template.Spider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.queue_name = "ctrip_hotel_list"
        self.redis = Redis()
        self.mongo = MongoInfo(
            database="ctrip"
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
                    url="https://hotels.ctrip.com/hotels/list",
                    params={
                        "cityId": "2553",
                        "provinceId": "22",
                        "districtId": "0",
                        "countryId": "1",
                        "cityName": "金堂",
                        "destName": "金堂",
                        "searchWord": "云顶牧场笙美度假村",
                        "searchType": "H",
                        "optionId": "96394948",
                        "checkin": "2025-11-07",
                        "checkout": "2025-11-08",
                        "crn": "1",
                        "listFilters": "29~1*29*1~2,31~96394948*31*96394948",
                        "locale": "zh-CN",
                        "old": "1",
                        "v2_mod": "9",
                        "v2_version": "E"
                    },
                    timeout=10,
                    headers={
                        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
                        'cache-control': 'max-age=0',
                        'priority': 'u=0, i',
                        'referer': 'https://hotels.ctrip.com/hotels/5951604.html?cityid=7553',
                        'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
                        'sec-ch-ua-mobile': '?0',
                        'sec-ch-ua-platform': '"Windows"',
                        'sec-fetch-dest': 'document',
                        'sec-fetch-mode': 'navigate',
                        'sec-fetch-site': 'same-origin',
                        'sec-fetch-user': '?1',
                        'upgrade-insecure-requests': '1',
                        'user-agent': user_agent.mobile(),
                        'Cookie': 'UBT_VID=1762407890488.8edfuMqKRbty; MKT_CKID=1762407890615.5qvdi.uzir; GUID=09031167210262527536; _RGUID=73e95b60-58ce-4bb9-a58e-4e3caad3a677; ibulocale=zh_cn; cookiePricesDisplayed=CNY; ibu_country=CN; GUID=09031167210262527536; nfes_isSupportWebP=1; _abtest_userid=c64b4f61-9df0-42a1-9b75-2f7827ac9f9d; IBU_showtotalamt=2; Hm_lvt_4a51227696a44e11b0c61f6105dc4ee4=1762410411,1762410816,1762411291,1762411804; HMACCOUNT=47D24B2967ECEBC9; Hm_lvt_a8d6737197d542432f4ff4abc6e06384=1762410441,1762410829,1762411299,1762411812; HMACCOUNT=47D24B2967ECEBC9; nfes_isSupportWebP=1; _RF1=240e%3A382%3A501%3A6000%3A796c%3A967%3A2519%3A2a13; _RSG=vkapO1sMfF7tPwqgoZJEMA; _RDG=281ca9eeb5ac0b219c35f2ae8bb3346850; ibu_h5_local=zh-cn; _ubtstatus=%7B%22vid%22%3A%221762407890488.8edfuMqKRbty%22%2C%22sid%22%3A1%2C%22pvid%22%3A33%2C%22pid%22%3A101021%7D; _bfaStatusPVSend=1; _bfi=p1%3D101021%26p2%3D0%26v1%3D33%26v2%3D0; _bfaStatus=success; StartCity_Pkg=PkgStartCity=2; Session=smartlinkcode=U130026&smartlinklanguage=zh&SmartLinkKeyWord=&SmartLinkQuary=&SmartLinkHost=; _lizard_LZ=LHUYNBaIGAdX-kWQqRZf9rcPSjzxK0vMO3uDm8EpweF64Cli52bTJs7ytnh1oVg+; cticket=74DC32B657CB759DF9E5197D8B94D29E31BCF1E956F7850900381CA23AC1E348; login_type=0; login_uid=""; DUID=u=8635C223556AA173FC00F2B155D2E9A9&v=0; IsNonUser=F; AHeadUserInfo=VipGrade=0&VipGradeName=%C6%D5%CD%A8%BB%E1%D4%B1&UserName=&NoReadMessageCount=0; _udl=708D70C2B179E2F91CC5ED1C2CCE362D; intl_ht1=h4%3D25_109340366%2C2553_96394948%2C7553_5951604; ibulanguage=ZH-CN; _ga_9BZF483VNQ=GS2.1.s1762510599$o5$g0$t1762510599$j60$l0$h0; Hm_lpvt_a8d6737197d542432f4ff4abc6e06384=1762510600; MKT_Pagesource=H5; _ga=GA1.2.1856492315.1762409715; _gid=GA1.2.1056032889.1762510603; _ga_5DVRDQD429=GS2.2.s1762510599$o5$g1$t1762510602$j57$l0$h1580267571; _ga_B77BES1Z8Z=GS2.2.s1762510599$o5$g1$t1762510602$j57$l0$h0; Union=OUID=&AllianceID=4897&SID=353693&SourceID=&AppID=&OpenID=&exmktID=&createtime=1762510616&Expires=1763115416311; MKT_OrderClick=ASID=4897353693&AID=4897&CSID=353693&OUID=&CT=1762510616313&CURL=https%3A%2F%2Fm.ctrip.com%2Fwebapp%2Fhotels%2Fhotelsearch%2FlistPage%3Fd-country%3D1%26d-city%3D25%26d-type%3DMAINLAND%26d-name%3D%255B%2522%25E5%258E%25A6%25E9%2597%25A8%2522%252C%2522%2522%252C%2522%2522%252C%2522%25E4%25B8%25AD%25E5%259B%25BD%2522%252C%2522%25E5%258E%25A6%25E9%2597%25A8%2522%255D%26c-in%3D2025-11-07%26c-out%3D2025-11-08%26c-rooms%3D1%26s-filters%3D%255B%255B%25221%25E6%2588%2590%25E4%25BA%25BA%252C0%25E5%2584%25BF%25E7%25AB%25A5%2522%252C%252229%257C1%2522%252C%252229%2522%252C%25221%257C1%2522%252C%2522%2522%252C%25222%2522%252C%2522%2522%252C%2522%2522%252C%2522%2522%252C%2522%2522%252C%2522%2522%252Cnull%255D%252C%255B%2522%25E5%258E%25A6%25E9%2597%25A8%25E5%2585%25B4%25E8%258D%25A3%25E5%259B%25BD%25E9%2599%2585%25E9%2585%2592%25E5%25BA%2597(%25E5%2590%258C%25E5%25AE%2589%25E7%258E%25AF%25E5%259F%258E%25E5%258D%2597%25E8%25B7%25AF%25E5%25BA%2597)%2522%252C%252231%257C109340366%2522%252C%252231%2522%252C%2522109340366%2522%252C%2522%2522%252C%2522%2522%252C%2522%2522%252C0%252C%2522%255B%255D%2522%252C%2522%255B%255D%2522%252C%252224.704684%257C118.145581%257C1%2522%252C%2522KeywordSearch%2522%255D%255D%26locale%3Dzh-CN%26allianceid%3D4897%26sid%3D353693%26curr%3DCNY%26source-tag%3D10650146790%26extra%3D%255B%257B%2522isVoiceSearch%2522%253A%25220%2522%257D%252C%257B%257D%252C%257B%2522isSemanticSearch%2522%253A%25220%2522%257D%252C%257B%2522250728_HTL_HotpoiXJK%2522%253A%2522%2522%257D%252C%257B%2522searchType%2522%253A%2522search_page%2522%257D%255D%26s-keyword%3D%255B%2522%25E5%258E%25A6%25E9%2597%25A8%25E5%2585%25B4%25E8%258D%25A3%25E5%259B%25BD%25E9%2599%2585%25E9%2585%2592%25E5%25BA%2597(%25E5%2590%258C%25E5%25AE%2589%25E7%258E%25AF%25E5%259F%258E%25E5%258D%2597%25E8%25B7%25AF%25E5%25BA%2597)%2522%252C%252231%257C109340366%2522%252C%252231%2522%252C%2522109340366%2522%252C%2522%2522%252C%2522%2522%252C%2522%2522%252C0%252C%2522%255B%255D%2522%252C%2522%255B%255D%2522%252C%252224.704684%257C118.145581%257C1%2522%255D%26page-token%3De93f3cfa-e1a1-4bcf-8a7a-52b358289d84%26dplinktracelogid%3Db22840e537d4b5b55494522b408f246c%26keywordsource%3Dsearchrecomdclick%26destinationsource%3Dsearchrecomdclick%26userActionTrace%3D%257B%2522associationToken%2522%253A%2522keyword_109340366%2522%252C%2522associationTraceId%2522%253A%2522100025527-0a63c03c-489586-735258%2522%252C%2522destinationId%2522%253A%2522%2522%252C%2522destinationType%2522%253A%2522%2522%252C%2522keywordType%2522%253A%25221%2522%252C%2522keywordId%2522%253A%2522109340366%2522%252C%2522keywordSource%2522%253A%2522searchrecomdclick%2522%252C%2522frompage%2522%253A%2522keyword%2522%252C%2522sourcePage%2522%253A%2522inquire%2522%252C%2522sourceType%2522%253A%2522keyword%2522%252C%2522channeltype%2522%253A%2522h5%2522%257D&VAL={"h5_vid":"1762407890488.8edfuMqKRbty"}; ibusite=CN; ibugroup=ctrip; Hm_lpvt_4a51227696a44e11b0c61f6105dc4ee4=1762511126; _jzqco=%7C%7C%7C%7C1762509076927%7C1.1687250969.1762407890613.1762510600196.1762511126552.1762510600196.1762511126552.0.0.0.48.48; _bfa=1.1762407890488.8edfuMqKRbty.1.1762510615873.1762511131159.5.12.10650171192; ibu_hotel_search_date=%7B%22checkIn%22%3A%222025-11-07%22%2C%22checkOut%22%3A%222025-11-08%22%7D; ibu_hotel_search_target=%7B%22countryId%22%3A1%2C%22provinceId%22%3A22%2C%22searchWord%22%3A%22%E4%BA%91%E9%A1%B6%E7%89%A7%E5%9C%BA%E7%AC%99%E7%BE%8E%E5%BA%A6%E5%81%87%E6%9D%91%22%2C%22cityId%22%3A2553%2C%22searchType%22%3A%22%22%2C%22searchValue%22%3A%22%22%7D; ibu_hotel_search_crn_guest=%7B%22adult%22%3A2%2C%22children%22%3A0%2C%22ages%22%3A%22%22%2C%22crn%22%3A1%7D; oldCurrency=CNY; IBU_showtotalamt=2; cookiePricesDisplayed=CNY; ibulanguage=ZH-CN; ibulocale=zh_cn; GUID=09031167210262527536; ibu_country=CN; ibugroup=ctrip; ibusite=CN'
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

        if "priceInfo" in response.text:
            loguru.logger.info("请求成功！！！！！！！！")
            time.sleep(10)
            raise Failure
        raise Success

    def init_seeds(self):
        return [{"hotel_id": 123}]


if __name__ == "__main__":
    proxy = {
        'ref': "bricks.lib.proxies.RedisProxy",
        'key': 'proxy_set',

    }
    spider = Detail(
        concurrency=1,
        **{"init.queue.size": 1000000},
        task_queue=RedisQueue(),
        downloader=go_requests.Downloader(),
        proxy=proxy

    )

    # spider.run(task_name='spider')
    spider.survey({
        "hotel_id": 1209067
    })
