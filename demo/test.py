import redis
from bricks import Request
from bricks.downloader.go_requests import Downloader

if __name__ == '__main__':
    # hotel_name = "邛崃十方堂酒店"
    # downloader = Downloader()
    # redis = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)
    # proxy_list = list(redis.smembers('proxy_set'))
    # proxies = "http://" + proxy_list[0]
    # redis.srem('proxy_set', proxy_list[0])
    # rsp = downloader.fetch(
    #     Request(
    #         # url="https://gdupi/api/search/all?sort=rel&pagingIndex=1&pagingSize=40&viewType=list&productSet=total&query=iphone+16+pro&origQuery=iphone+16+pro&adQuery=iphone+16+pro&iq=&eq=&xq=&catId=50000247&minPrice=700000&maxPrice=1400000",
    #         url="https://m.ctrip.com/restapi/soa2/30668/search",
    #         method="POST",
    #         body={
    #             "action": "online",
    #             "source": "globalonline",
    #             "keyword": hotel_name
    #         },
    #         timeout=20,
    #         max_retry=5,
    #         headers={
    #           'accept': '*/*',
    #           'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    #           'content-type': 'application/x-www-form-urlencoded',
    #           'origin': 'https://hotels.ctrip.com',
    #           'priority': 'u=1, i',
    #           'referer': 'https://hotels.ctrip.com/',
    #           'sec-ch-ua': '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    #           'sec-ch-ua-mobile': '?0',
    #           'sec-ch-ua-platform': '"Windows"',
    #           'sec-fetch-dest': 'empty',
    #           'sec-fetch-mode': 'cors',
    #           'sec-fetch-site': 'same-site',
    #           'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
    #         },
    #         proxies=proxies
    #
    #         # use_session=True
    #     )
    # )
    # print(rsp.text)
    # print(rsp.error)
    # print(rsp.status_code)
    # print(rsp.request.proxies)

    # import requests
    #
    # r = requests.post("http://127.0.0.1:5000/render_hotel", json={"hotel_name": "测试"})
    # print(r.status_code)
    # print(r.text[:200])
    cookies = {
        "UBT_VID": "1762418797556.a198ZPlQfLuJ",
        "MKT_CKID": "1762418797735.84z1i.1j3m",
        "_RGUID": "12c630d0-9de7-4aa9-8d9d-cf8383ae27d1",
        "Hm_lvt_a8d6737197d542432f4ff4abc6e06384": "1763184531",
        "HMACCOUNT": "62D091900B51643A",
        "Union": "OUID=Singapore&AllianceID=4899&SID=2611971&SourceID=&createtime=1763184532&Expires=1763789331525",
        "MKT_OrderClick": "ASID=48992611971&AID=4899&CSID=2611971&OUID=Singapore&CT=1763184531526&CURL=https%3A%2F%2Fwww.ctrip.com%2F%3Fsid%3D2611971%26allianceid%3D4899%26ouid%3DSingapore%26gclsrc%3Daw.ds%26gad_source%3D1%26gad_campaignid%3D8502960924%26gbraid%3D0AAAAACtzBae4QRn-UpHqI9KUXRlMxCjpP%26gclid%3DCjwKCAiAw9vIBhBBEiwAraSATk2Gq5bXMbm0IpC9-mmsM3C6clYgoFQqnRbfyhDfQC3t-CfVBVArRRoCq8cQAvD_BwE%26keywordid%3D3228541865-86606356056&VAL={\"pc_vid\":\"1762418797556.a198ZPlQfLuJ\"}",
        "_gcl_aw": "GCL.1763184532.CjwKCAiAw9vIBhBBEiwAraSATk2Gq5bXMbm0IpC9-mmsM3C6clYgoFQqnRbfyhDfQC3t-CfVBVArRRoCq8cQAvD_BwE",
        "_gcl_dc": "GCL.1763184532.CjwKCAiAw9vIBhBBEiwAraSATk2Gq5bXMbm0IpC9-mmsM3C6clYgoFQqnRbfyhDfQC3t-CfVBVArRRoCq8cQAvD_BwE",
        "GUID": "09031154211350623800",
        "_ga": "GA1.1.1272781382.1763184532",
        "_gcl_gs": "2.1.k1$i1763184530$u167964915",
        "MKT_Pagesource": "PC",
        "nfes_isSupportWebP": "1",
        "cticket": "1AE02F0B0E4F98649EADA281C89C3140F0ACDD97CA16180726FA4EEDCA3AFF97",
        "login_type": "0",
        "login_uid": "6A8B00D9AB6829EFA4425BCA241D172E",
        "DUID": "u=B5F4E2459095FB1BB3C175664D977CD8&v=0",
        "IsNonUser": "F",
        "AHeadUserInfo": "VipGrade=0&VipGradeName=%C6%D5%CD%A8%BB%E1%D4%B1&UserName=&NoReadMessageCount=0",
        "_udl": "708D70C2B179E2F91CC5ED1C2CCE362D",
        "Hm_lpvt_a8d6737197d542432f4ff4abc6e06384": "1763184781",
        "_ga_9BZF483VNQ": "GS2.1.s1763184531$o1$g1$t1763184781$j59$l0$h0",
        "_ga_5DVRDQD429": "GS2.1.s1763184531$o1$g1$t1763184782$j58$l0$h601373868",
        "_ga_B77BES1Z8Z": "GS2.1.s1763184531$o1$g1$t1763184782$j58$l0$h0",
        "ibulocale": "zh_cn",
        "cookiePricesDisplayed": "CNY",
        "IBU_showtotalamt": "2",
        "_abtest_userid": "0ee1c9f4-eb97-4188-8399-175060be307e",
        "ibulanguage": "ZH-CN",
        "_jzqco": "%7C%7C%7C%7C1763184531842%7C1.1242032049.1762418797734.1763184861217.1763184866867.1763184861217.1763184866867.0.0.0.18.18",
        "_bfa": "1.1762418797556.a198ZPlQfLuJ.1.1763184861584.1763184866848.5.6.10650171194"
    }
    # 方法1：最简洁的方式
    cookies_str = "; ".join([f"{key}={value}" for key, value in cookies.items()])
    print(cookies_str)


