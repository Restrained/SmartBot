import json
import requests


def extract_unused_proxies_keep_raw(api_proxy_text: str, json_file_path: str, other_proxies: list, output_file: str):
    """
    api_proxy_text: API 原始代理文本 ip|port|user|pwd|expire
    json_file_path: JSON 文件路径
    other_proxies: 其他正在使用的代理 http://user:pwd@ip:port
    output_file: 输出文件路径
    """

    # 1. API 原始代理行（保持原样）
    api_raw_lines = [line.strip() for line in api_proxy_text.strip().split("\n") if line.strip()]

    # 2. 抽取 key 用来比对
    def extract_key_api_raw(line: str):
        parts = line.split("|")
        ip, port, user, pwd = parts[:4]
        return f"{ip}|{port}|{user}|{pwd}"

    api_keys = {extract_key_api_raw(line): line for line in api_raw_lines}

    # -------------------------
    # 3. JSON 文件中的已使用代理
    # -------------------------
    used_keys = set()

    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        proxy_http = item.get("proxy", {}).get("http")
        if proxy_http:
            try:
                proxy_http = proxy_http.replace("http://", "")
                user_pwd, ip_port = proxy_http.split("@")
                user, pwd = user_pwd.split(":")
                ip, port = ip_port.split(":")
                key = f"{ip}|{port}|{user}|{pwd}"
                used_keys.add(key)
            except:
                continue

    # -------------------------
    # 4. other_proxies 列表中正在使用的代理
    # -------------------------
    def parse_other(proxy):
        # http://user:pwd@ip:port
        try:
            proxy = proxy.replace("http://", "")
            user_pwd, ip_port = proxy.split("@")
            user, pwd = user_pwd.split(":")
            ip, port = ip_port.split(":")
            return f"{ip}|{port}|{user}|{pwd}"
        except:
            return None

    for p in other_proxies:
        key = parse_other(p)
        if key:
            used_keys.add(key)

    # -------------------------
    # 5. 最终未使用代理 = API 中有 但 不在 used_keys
    # -------------------------
    unused_raw_lines = [
        raw_line for k, raw_line in api_keys.items() if k not in used_keys
    ]

    # -------------------------
    # 6. 写入输出文件
    # -------------------------
    with open(output_file, "w", encoding="utf-8") as f:
        for line in unused_raw_lines:
            f.write(line + "\n")

    return unused_raw_lines


# -----------------------------
# 示例调用
# -----------------------------
if __name__ == '__main__':
    api = "http://www.tianxingip.com/proxy/apigetdata?token=NMb15fGy6Cfk2U2xjLUV2QMQ8aUzTz5VfTyYglxMVFcGO11Xjx4HiV6GSPl5QHgYV2NYdDdNMb45v-w7Cfk2P6_&orderId=0&format=1&char=1&type=1&customizechar=&customizetype=&outfild=0"
    response = requests.get(api)
    api_text = response.text

    other_proxies = [
        "http://lyso20p25:FvnNfJmD@111.124.196.64:2018",
        "http://lyso20p54:RGDAjuEp@60.15.52.161:8888",
        "http://nucl21c38:ceDmzFfg@49.119.135.121:2018",
        "http://znuq17j6:s7yEjAYc@116.179.48.37:8888",
        "http://vbqu21a30:fZxJFiKg@120.240.118.91:2018",
        "http://xcdata01:xcdata01@180.97.244.236:2018",
        "http://xcdata01:xcdata01@171.108.221.76:2018",
        "http://xcdata01:xcdata01@180.130.103.212:8888",
        "http://xcdata01:xcdata01@112.30.173.175:2018",
        "http://nucl21c3:nUYDG4Vs@42.225.103.6:8888",
        "http://lyso20p12:SWpHNz4x@61.152.118.15:2018",
        "http://vbqu21a23:GU4Dj3yp@60.14.58.219:8888",
        "http://xcdata01:xcdata01@111.177.41.87:2018",
        "http://nucl21c26:taMe2Cm3@118.213.94.161:2018",
        "http://lyso20p17:DPfM2FAW@42.101.81.85:2018",
        "http://nucl21c33:V4sAJq8b@124.225.171.89:2018",
        "http://xcdata01:xcdata01@14.119.108.63:2018",
        "http://xcdata01:xcdata01@120.71.150.136:2018",
        "http://xinw18i16:JdDUNsB6@112.132.240.34:8888",
        "http://xcdata01:xcdata01@112.195.22.9:8888",
        "http://xcdata01:xcdata01@111.172.245.225:2018",
        "http://xcdata01:xcdata01@124.236.113.44:2021",
        "http://xcdata01:xcdata01@1.193.221.252:2018",
        "http://lyso20p66:tfbvMwZY@49.7.135.118:2018",
        "http://xcdata01:xcdata01@60.167.183.114:2018",
        "http://xcdata01:xcdata01@113.142.203.37:2018",
        "http://xcdata01:xcdata01@182.131.27.12:2018",
        "http://xcdata01:xcdata01@106.4.20.235:2018",
        "http://xcdata01:xcdata01@36.156.74.121:2018",
        "http://znuq17j4:nPFxXdDB@110.166.74.47:2018",
        "http://lyso20p48:zfvhPIEM@113.5.175.114:8888",
        "http://vbqu21a5:AIwr4S7G@120.221.249.79:2018",
        "http://lyso20p64:NijSfWwe@118.183.44.105:2018",
        "http://xcdata01:xcdata01@119.96.32.90:2018",
        "http://xcdata01:xcdata01@36.150.45.192:2018",
        "http://lyso20p32:dse7VDTn@36.248.75.74:2018"
    ]

    unused = extract_unused_proxies_keep_raw(
        api_proxy_text=api_text,
        json_file_path=r"D:\projects\SmartBot\proxies.json",
        other_proxies=other_proxies,
        output_file="unused_proxy_raw.txt"
    )

    print("未使用代理：", unused)
