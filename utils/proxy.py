import time
import requests
import redis

def fetch_and_store_proxies(url, redis_host, redis_port, redis_db, redis_set):
    # 连接到 Redis
    r = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db)

    while True:
        try:
            # 如果 set 的数量超过200，停止请求并休眠10秒再继续
            if r.scard(redis_set) > 50:
                print("代理数量已达到200，停止请求并休眠10秒。")
                time.sleep(5)
                continue
            # 发送 HTTP 请求获取代理IP列表
            response = requests.get(url)
            response.raise_for_status()  # 检查请求是否成功


            # 解析响应内容，并将代理IP添加到 Redis 的 set 中
            proxies = response.text.splitlines()
            for proxy in proxies:
                r.sadd(redis_set, proxy)

            print("成功获取并存储代理IP。")

        except Exception as e:
            print(f"获取代理IP出错：{e}")

        # 每5秒执行一次
        time.sleep(2)

if __name__ == "__main__":
    # 提取链接
    proxy_url = r"https://share.proxy.qg.net/get?key=UW10RFZH&num=1&area=&isp=0&format=txt&seq=\r\n&distinct=false"

    # Redis 信息
    redis_host = "localhost"
    redis_port = 6379
    redis_db = 0
    redis_set = "proxy_set"  # 指定存储代理IP的 set 名称

    # 执行函数
    fetch_and_store_proxies(proxy_url, redis_host, redis_port, redis_db, redis_set)
