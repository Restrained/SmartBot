import time
import threading
import requests


class RegisterLoopWorker(threading.Thread):
    """ 单个接口的自动注册循环 """

    def __init__(self, base_url, count=5, interval_minutes=5):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.count = count
        self.interval_minutes = interval_minutes

        self.auto_url = f"{self.base_url}/xc/auto_register?count={self.count}"
        self.list_url = f"{self.base_url}/xc/getCookieList"

    def run(self):
        print(f"=== 接口 {self.base_url} 自动注册循环已启动 ===\n")

        while True:
            try:
                print(f"[{self.base_url}] 请求 auto_register: {self.auto_url}")
                r = requests.get(self.auto_url, timeout=30)
                print(f"[{self.base_url}] auto_register 状态码：{r.status_code}")
            except Exception as e:
                print(f"[{self.base_url}] auto_register 请求失败: {e}")

            print(f"[{self.base_url}] 休眠 {self.interval_minutes} 分钟...\n")
            time.sleep(self.interval_minutes * 60)

            try:
                print(f"[{self.base_url}] 请求 getCookieList: {self.list_url}")
                r = requests.get(self.list_url, timeout=30)
                data = r.json()

                used_list = data.get("used", [])
                count_used = len(used_list)

                print(f"[{self.base_url}] >>> used 列表数量 = {count_used}\n")

            except Exception as e:
                print(f"[{self.base_url}] getCookieList 请求失败: {e}")

            print(f"[{self.base_url}] 下一轮开始...\n")
            time.sleep(1)


def auto_register_multi(base_urls, count=5, interval_minutes=5):
    """
    同时启动多个接口的自动注册循环
    base_urls: ["http://8.162.5.219:8004", "http://121.40.66.240:8004"]
    """
    workers = []

    for url in base_urls:
        worker = RegisterLoopWorker(url, count, interval_minutes)
        worker.daemon = True
        worker.start()
        workers.append(worker)

    print("\n=== 所有接口自动注册已全部启动 ===\n")

    # 主线程保持运行
    while True:
        time.sleep(10)


if __name__ == "__main__":
    base_list = [
        "http://8.162.5.219:8004",
        "http://121.40.66.240:8004"
    ]

    auto_register_multi(base_list, count=5, interval_minutes=5)
