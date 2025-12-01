import datetime
import json
import os
import re
import threading
import time
import uuid
from typing import Dict, List
from urllib.parse import quote

import requests
import concurrent.futures

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from bricks.db.redis_ import Redis
from loguru import logger

from config.settings import REDIS_HOST
from db.mongo import MongoClientSingleton
from parse_detail import parse_room
from utils.date_switch import parse_checkin_checkout
from utils.task_platform_login import rsa_encrypt_base64

# =========================
# 模块使用常量
# =========================
REDIS_KEY = "ctrip_ck"
MAX_RETRIES = 3


class SchedulerAuto:
    """
    单用户任务是串行的，也就是说单个用户只有执行完第一个任务才能接收下一个
    """

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.token = None
        self.cookie_col = "cookie_use_log"

        # ✅ 初始化 MongoDB
        self.redis = Redis(host=REDIS_HOST)
        self.mongo = MongoClientSingleton(db_name="ctrip")

        # 添加线程锁确保单个账号串行执行
        self.lock = threading.Lock()



    def login(self):
        # 登录接口地址（换成你实际的平台登录接口）
        api = "http://47.101.140.209/crowd/task/login"

        body = rsa_encrypt_base64(f"{self.username}_{self.password}")

        # 可选请求头（根据平台要求修改）
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }

        # 发送请求
        response = requests.post(api, body, headers=headers)

        # 解析响应
        try:
            if response.status_code == 200:
                res_json = response.json()
                if res_json.get("success") and res_json.get("code") == 200:
                    self.token = res_json.get("data")
                    logger.info(f"》》》》》step1. {self.username}用户登录成功\n\n")

                else:
                    logger.warning("❌ 登录失败:", res_json.get("msg"))
            else:
                logger.error("❌ 请求失败，状态码:", response.status_code)
        except Exception as e:
            logger.error(f"❌ 登录异常: {e}")

    def get_tasks(self):
        api = "http://47.101.140.209/crowd/task/listTask"
        if self.token:
            params = {
                "token": self.token,
            }
            try:
                response = requests.get(api, params)
                raw_task = response.json()
                tasks = self.task_filter(raw_task)
                return tasks
            except Exception as e:
                logger.warning(f"获取任务列表请求出错, 错误原因{e}")
                return []
        else:
            logger.warning("登录失败，请检查登录状态")
        return []

    @staticmethod
    def extract_dates(text: str):
        """
        从字符串中提取入店时间和离店时间
        例如输入："入店时间：2025-11-09  离店时间：2025-11-10"
        返回 ("2025-11-09", "2025-11-10")
        """
        pattern = r".*?店时间：(\d{4}-\d{2}-\d{2})\s*离店时间：(\d{4}-\d{2}-\d{2})"
        match = re.search(pattern, text)
        if match:
            check_in, check_out = match.groups()
            return check_in, check_out
        return None, None

    def get_running_task(self):
        """
        获取当前账号是否存在进行中任务
        :return:
        """
        result = []
        api = "http://47.101.140.209/crowd/task/queryClaimRecordList"

        params = {
            "type": "today",
            "claimStatus": "CLAIMED",
            "pageSize": "10",
            "pageNo": "1",
            "token": self.token
        }

        try:
            response = requests.get(api, params)
            if all([
                response.status_code == 200,
                response.json()["code"] == 200,
                response.json()["msg"] == "正常返回"
            ]):
                data = response.json()["data"]
                if data:
                    task_list = data.get("claimRecordVOList")
                    if task_list:
                        item = task_list[0]
                        result.append({
                            "task_id": item["taskSetId"],
                            "task_name": item["shidName"],
                            "task_type": item["taskType"],
                            "valid_task_num": 1,
                            "running_task": 1
                        })

        except Exception as e:
            logger.error(f"获取正在运行中结果报错， 错误原因{e}")
        return result

    def task_filter(self, raw_tasks: Dict):
        """
        过滤国内且余量大于0的任务进行下一步分发
        :param raw_tasks:
        :return:
        """
        result = []
        data = raw_tasks.get("data", [])
        for item in data:
            task_site = item.get("taskSite")
            biz_type = item.get("bizType")
            valid_task_num = item.get("validTaskNum")
            task_name = item.get("taskName")
            day_task_num_limit = int(item.get("dayTaskNumLimit"))
            claim_task_num = item.get("claimTaskNum")
            if all([
                claim_task_num < day_task_num_limit,
                task_site == "XC",
                biz_type == "HOTEL",
                valid_task_num > 0,
                "国内" in task_name,
                # todo 暂时只跑详情
                item["taskType"]=="XC_ROOM_DETAIL_RP_PIC_DISCOUNT",
            ]):
                try:
                    result.append({
                        "task_id":  item["id"],
                        "task_name":  task_name,
                        "task_type": item["taskType"],
                        "valid_task_num": valid_task_num,
                    })
                except KeyError:
                    logger.error("返回的任务列表格式有误，请检查！！！")
        if not result:
            logger.warning("当前账号无可领任务，请切换账号")
        return result

    def task_fetcher(self, original_task_info: dict) -> Dict:
        """
        根据可用的任务id实际领取任务
        返回酒店一些必要的参数
        :return:
        """
        city, hotel_name, check_in, check_out, claim_id = "", "", "", "", ""
        room_info = []
        if original_task_info.get("running_task") == 1:
            api = "http://47.101.140.209/crowd/task/queryClaimTemplateTask"
        else:
            api = "http://47.101.140.209/crowd/task/claimTemplateTask"

        params = {
            "taskSetId": original_task_info["task_id"],
            "token": self.token,
        }
        try:
            response = requests.get(api, params)
            if all([
                response.status_code == 200,
                response.json()["code"] == 200,
                response.json()["msg"] == "正常返回"
            ]):
                data = response.json()["data"]
                claim_id = data["claimId"]
                task_info = data["taskInfo"]
                for item in task_info:
                    label = item["label"]
                    if label == "所在城市":
                        city = item["value"]
                    elif label == "酒店名称":
                        hotel_name = item["value"]
                task_group = data["taskGroup"][0]
                title = task_group["title"]
                task_list = task_group["taskList"]
                if  "离店时间" in title:
                    check_in, check_out = self.extract_dates(title)
                for item in task_list:
                    room_id = item["key"]
                    raw_room_name = item["title"]

                    if raw_room_name == '列表页信息':
                        room_name = raw_room_name
                    else:
                        try:
                            room_pattern = r'房型：(.*?)\n'
                            room_match = re.search(room_pattern, raw_room_name)
                            room_name = room_match.group(1).strip()
                        except:
                            raise ValueError(f"提取房型名称报错， 错误字符串{raw_room_name}")


                    room_info.append({
                        "key": room_id,
                        "title": room_name
                    })
            elif response and response.json()["msg"] == "当日无待领取任务":
                return {}


        except Exception as e:
            logger.error(f"领取任务出现异常，报错原因{e}")
        return {
            "city": city,
            "hotel_name": hotel_name,
            "claim_id": claim_id,
            "check_in": check_in,
            "check_out": check_out,
            "task_type": original_task_info["task_type"],
            "room_info": room_info,
        }


    def add_task_to_redis(self, queue_name: str, task_info: dict):
        """添加任务到 Redis 队列，使用固定排序的 JSON"""
        # 使用 sort_keys=True 确保字段按字母顺序排序
        task_json = json.dumps(task_info, sort_keys=True, ensure_ascii=False)
        self.redis.sadd(queue_name, task_json)
        logger.info(f"任务已添加到 {queue_name}: {task_info}")

    def send_task(self, task_info: Dict):
        """发送任务并等待结果 - 支持305错误处理"""
        # 根据任务类型确定队列
        if task_info["task_type"] == "XC_ROOM_DETAIL_RP_PIC_DISCOUNT":
            queue_name = "ctrip_detail_queue_v3"
            collection = "ctrip_detail_results"
        elif task_info["task_type"] == "XC_LIST_TEMPLATE_PIC_DISCOUNT":
            queue_name = "ctrip_list_queue"
            collection = "ctrip_list_results"
        else:
            raise ValueError(f"未知任务类型 {task_info['task_type']}，请检查")

        # 1. 检查是否已有结果
        existing_result = self.get_task_result(task_info, collection)
        if existing_result:
            is_success, checked_result = self.handle_task_result(existing_result, task_info["task_type"])

            # 检查是否是305错误
            if self.is_305_response(existing_result):
                logger.warning("✅ 发现305错误结果，需要取消任务")
                return {"code": 305, "msg": "携程服务器内异常,放弃任务", "need_cancel": True}

            if is_success and self.validate_response_data(checked_result, task_info["task_type"]):
                logger.info("✅ 发现已有成功结果，直接使用")
                return checked_result

        # 2. 推送任务到队列
        self.add_task_to_redis(queue_name, task_info)
        logger.info(f"✅ 投放任务到 {queue_name}...")

        # 3. 等待任务结果，支持305错误检测
        start_time = time.time()
        timeout = 240
        poll_interval = 5

        while time.time() - start_time < timeout:
            result = self.get_task_result(task_info, collection)
            if result:
                # 优先检查305错误
                if self.is_305_response(result):
                    logger.warning("✅ 获取到305错误结果，需要取消任务")
                    return {"code": 305, "msg": "携程服务器内异常,放弃任务", "need_cancel": True}

                is_success, checked_result = self.handle_task_result(result, task_info["task_type"])
                if is_success and self.validate_response_data(checked_result, task_info["task_type"]):
                    logger.info("✅ 获取到有效数据")
                    return checked_result

            time.sleep(poll_interval)

        logger.warning(f"❌ 获取任务结果超时")
        return {"error": "timeout", "msg": "任务响应超时", "need_cancel": False}

    def is_305_response(self, response: dict) -> bool:
        """判断是否是305错误响应"""
        if not response or not isinstance(response, dict):
            return False
        return response.get("code") == 305

    def validate_response_data(self, response: dict, task_type: str) -> bool:
        """验证响应数据的完整性"""
        if not response or response.get("error"):
            return False

        # 检查是否是服务器错误响应
        if response.get("code") in [301, 303, 304, 305, 306, 307]:
            return False

        # 根据任务类型验证数据结构
        if task_type == "XC_ROOM_DETAIL_RP_PIC_DISCOUNT":
            # 验证详情任务的数据结构
            data = response.get("data", {})
            sale_room_map = data.get("saleRoomMap", {})
            if not sale_room_map:
                return False

            # 检查至少一个房型有价格信息
            for room in sale_room_map.values():
                price_info = room.get("priceInfo", {})
                if price_info.get("displayPrice", "").startswith("¥"):
                    return True
            return False

        else:
            # 列表任务的验证
            data = response.get("data", {})
            hotel_list = data.get("hotelList", [])
            if not hotel_list:
                return False

            # 检查酒店信息
            hotel = hotel_list[0]
            room_info = hotel.get("roomInfo", [])
            if room_info and room_info[0].get("priceInfo", {}).get("displayPrice", "").startswith("¥"):
                return True
            return False


    def screenshot(self, task_info: dict, response: dict = None):
        """生成渲染数据并调用 Flask 接口渲染 + Playwright 截图"""

        import os, requests
        from playwright.sync_api import sync_playwright

        hotel_name = task_info["hotel_name"]
        check_in = task_info["check_in"]
        check_out = task_info["check_out"]
        date_dict = parse_checkin_checkout(check_in, check_out)

        # 房型数据
        rooms, dialogs = parse_room(json_content=response)
        room_info_list = task_info.get("room_info", [])

        # 初始化路径
        today = datetime.datetime.now().strftime("%Y%m%d")
        out_dir = f"screenshots/{today}/{hotel_name}"
        os.makedirs(out_dir, exist_ok=True)

        # 初始化 screenshots 字段
        for room_item in room_info_list:
            room_item["screenshots"] = []

        flask_render_room_url = "http://127.0.0.1:5000/render_room"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(**p.devices["iPhone X"])
            page = context.new_page()

            self.patch_page_rendering(page)

            # === 处理房型列表页 ===
            list_page_item = next((i for i in room_info_list if i["title"] == "列表页信息"), None)
            if not list_page_item:
                raise ValueError("房型列表页信息缺失")

            # 遍历每个房型（非列表页）
            for room_item in room_info_list:
                title = room_item["title"].strip()

                if title == "列表页信息":
                    continue

                logger.info(f"📸 开始处理房型：{title}")

                # 匹配房型数据
                target_rooms = [r for r in rooms if title == (r.get("name") or "")]
                if not target_rooms:
                    logger.warning(f"⚠ 未匹配到房型：{title}")
                    continue

                # 计算每种早餐的最低价 variant
                breakfast_map = self.compute_breakfast_lowest_variant(target_rooms)

                # 匹配对应弹窗
                matched_dialogs = [
                    d for d in dialogs
                    if d.get("room_code") and any(v.get("code") == d.get("room_code") for v in breakfast_map.values())
                ]

                # 构建渲染 payload
                payload = {
                    "hotel_name": hotel_name,
                    "checkin_date": date_dict["checkin_date"],
                    "checkin_day": date_dict["checkin_day"],
                    "checkout_date": date_dict["checkout_date"],
                    "checkout_day": date_dict["checkout_day"],
                    "stay_night": 1,
                    "rooms": list(breakfast_map.values()),
                    "dialog": matched_dialogs
                }

                # 调用 Flask
                resp = requests.post(flask_render_room_url, json=payload)
                if resp.status_code != 200:
                    logger.error("❌ 渲染失败")
                    continue

                # 页面加载
                page.set_content(resp.text, wait_until="networkidle")
                page.wait_for_timeout(500)

                # ✔ 截图列表页
                list_img = self.capture_room_list_item(page, title, out_dir)
                list_page_item["screenshots"].append(list_img)

                # ✔ 截图每种早餐对应弹窗
                for b_type, variant in breakfast_map.items():
                    variant_code = variant.get("code")
                    dialog_img = self.capture_dialog(page, variant_code, out_dir)
                    if dialog_img:
                        room_item["screenshots"].append(dialog_img)

            browser.close()

        return room_info_list

    def patch_page_rendering(self, page):
        page.evaluate("""
            () => {
                document.body.style.overflow = 'hidden';
                document.body.style.webkitFontSmoothing = 'antialiased';
                document.body.style.mozOsxFontSmoothing = 'grayscale';
                document.body.style.textRendering = 'optimizeLegibility';
            }
        """)
        page.add_style_tag(content="""
            * {
                image-rendering: crisp-edges !important;
                text-rendering: optimizeLegibility !important;
                -webkit-font-smoothing: antialiased !important;
            }
        """)

    def capture_room_list_item(self, page, title, out_dir):
        safe_title = title.replace("/", "_").replace(" ", "")
        img_path = os.path.join(out_dir, f"{uuid.uuid4().hex}_list.png")
        page.screenshot(path=img_path)
        logger.info(f"✔ 列表页截图完成: {img_path}")
        return img_path

    def compute_breakfast_lowest_variant(self, rooms):
        breakfast_types = ["无早餐", "1份早餐", "2份早餐"]

        result = {}
        for room in rooms:
            bf_raw = room.get("breakfast", "") or ""

            matched = next((b for b in breakfast_types if b in bf_raw), "无早餐")

            price = float(room.get("price", 1e9) or 1e9)

            if matched not in result or price < float(result[matched].get("price", 1e9)):
                result[matched] = room

        return result

    def capture_dialog(self, page, variant_code, out_dir):
        dialog_id = f"dialog-{variant_code}"
        btn_selector = f'.open-discount-btn[data-dialog-id="{dialog_id}"]'
        btn = page.query_selector(btn_selector)

        if not btn:
            logger.warning(f"⚠ 未找到弹窗按钮: {btn_selector}")
            return None

        try:
            btn.scroll_into_view_if_needed()
            page.wait_for_timeout(200)
            btn.click()
            page.wait_for_timeout(600)

            img_path = os.path.join(out_dir, f"{uuid.uuid4().hex}_dialog.png")
            page.screenshot(path=img_path)
            logger.info(f"✔ 弹窗截图成功: {img_path}")

            self.safe_close_dialog(page, variant_code)
            return img_path

        except Exception as e:
            logger.error(f"❌ 弹窗截图失败: {e}")
            return None

    def safe_close_dialog(self, page, variant_code):
        dialog_id = f"dialog-{variant_code}"
        close_selector = f'.close[data-dialog-id="{dialog_id}"]'

        try:
            btn = page.query_selector(close_selector)
            if btn:
                btn.scroll_into_view_if_needed()
                btn.click()
            else:
                mask = page.query_selector(f"#mask-{variant_code}")
                if mask:
                    mask.click()
                else:
                    page.mouse.click(10, 10)

            page.wait_for_timeout(200)
        except:
            page.mouse.click(10, 10)


    def get_task_result(self, task_info: Dict, collection: str, timeout: int = 120):
        """
        根据任务信息轮询 MongoDB 或 Redis 获取结果
        """
        response = {}
        check_in = task_info.get("check_in")
        check_out = task_info.get("check_out")
        hotel_name = task_info.get("hotel_name")

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        query = {"hotel_name": hotel_name, "check_in": check_in, "check_out": check_out, "date": today}

        # 假设结果是存入 MongoDB 的（也可改为 Redis）

        result = self.mongo.find_one(collection, query=query)
        if result:
            response = json.loads(result.get("response"))

        return response

    def handle_task_result(self, result: dict, task_type: str):
        """改进的结果检查逻辑，支持305错误"""
        if not result:
            return False, {"msg": "空结果"}

        # 检查305错误
        if result.get("code") == 305:
            return True, result  # 返回True表示需要特殊处理305错误

        result_str = json.dumps(result)

        # 检查错误情况
        if any(error in result_str for error in ["error", "timeout", "异常", "失败"]):
            return False, result

        if "priceInfo" in result_str:
            if task_type == "XC_ROOM_DETAIL_RP_PIC_DISCOUNT":
                if "totalPriceInfo" in result_str:
                    logger.info("✅ 详情任务数据正常")
                    return True, result
            else:
                if "tipAfterPrice" in result_str or "酒店已售罄" in result_str:
                    logger.info("✅ 列表任务数据正常")
                    return True, result

        return False, {"msg": "数据结构异常"}

    # ===== 第一步：请求 OSS 上传所需参数 =====
    def get_oss_upload_info(self, token, file_name):
        url = "http://47.101.140.209/crowd/task/getOssKey?token=" + token
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "http://47.101.140.209",
            "Referer": "http://47.101.140.209/crowd.html",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        }
        cookies = {"crowd-code": "759528"}
        payload = {
            "bizType": "HOTEL",
            "fileName": file_name,
            "token": token
        }
        while True:
            try:
                resp = requests.post(url, headers=headers, json=payload, cookies=cookies, verify=False)
                resp.raise_for_status()
                if resp.json() and resp.json()["msg"] == '正常返回':
                    data = resp.json()["data"]
                    logger.info("✅ 获取 OSS 上传参数成功")
                    return data
            except Exception as e:
                logger.warning(f"图片上传出现问题，错误原因{e}")
                time.sleep(2)

    # ===== 第二步：使用返回参数上传文件到 OSS =====
    def upload_to_oss(self, file_path, oss_info):
        url = f"https://{oss_info['url']}/"

        data = {
            "accessId": oss_info["accessId"],
            "ossKey": oss_info["ossKey"],
            "signature": oss_info["signature"],
            "expiration": oss_info["expiration"],
            "uuid": oss_info["uuid"],
            "policy": oss_info["policy"],
            "OSSAccessKeyId": oss_info["accessId"],
            "key": oss_info["ossKey"]
        }

        files = {
            "file": (file_path.split("/")[-1], open(file_path, "rb"), "image/png")
        }

        logger.info("📤 正在上传文件到 OSS ...")
        while True:
            try:
                resp = requests.post(url, data=data, files=files)
                resp.raise_for_status()
                break
            except Exception as e:
                logger.warning("上传文件到 OSS，错误原因{e}, 继续重试")
                time.sleep(2)

        if resp.status_code == 204:
            logger.info ("✅ 上传成功（OSS 无返回体）")
        else:
            logger.info("✅ 上传成功，响应：", resp.text)

    def submit_template_task(self, task_info, token, submit_task_map, claim_id, do_submit=True):
        """
        提交模板任务

        Args:
            token (str): 认证token
            submit_task_map (dict): 提交的任务映射，格式如：
                {
                    "1": ["path1.jpg", "path2.jpg"],
                    "2": ["path3.jpg", "path4.jpg"],
                    "3": ["path5.jpg", "path6.jpg"],
                    "list_1_2_3": ["path7.jpg", "path8.jpg", "path9.jpg"]
                }
            claim_id (int): 任务声明ID
            do_submit (bool): 是否实际提交，默认为False（测试用）

        Returns:
            dict: 服务器响应数据
            :param do_submit:
            :param claim_id:
            :param submit_task_map:
            :param token:
            :param task_info:
        """
        url = "http://47.101.140.209/crowd/task/submitTemplateTask?token=" + token
        headers = {
          'Accept': '*/*',
          'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
          'Connection': 'keep-alive',
          'Origin': 'http://47.101.140.209',
          'Referer': 'http://47.101.140.209/crowd.html',
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
          'content-type': 'application/json',
          'Cookie': 'crowd-code=759528'
        }

        # 准备请求数据
        payload = {
            "claimId": claim_id,
            "giveUpTaskMap": "{}",
            "submitTaskMap": json.dumps(submit_task_map, ensure_ascii=False),
            "doSubmit": do_submit,
            "token": token
        }

        # 发送请求
        resp = requests.post(
            url,
            headers=headers,
            json=payload,
            verify=False
        )

        resp.raise_for_status()
        response_data = resp.json()

        # logger.info(response_data)
        result = "Failure"
        if response_data and response_data.get("msg") == '未识别到匹配房型，请重试！':
            logger.warning("✅ 模板任务提交失败， 取消任务")
            self.cancel_task(token, claim_id)
        elif response_data and response_data.get("msg") == "正常返回":
            logger.info(f"》》》》》step6. {task_info['hotel_name']} 任务提交成功\n\n")
            result = "Success"
        elif  response_data and any(
                [
                    response_data.get("msg") == '任务集已失效，请刷新后重试',
                    response_data.get("msg") == '找不到该任务认领记录',

                ]):
            logger.info("任务集已失效，请刷新后重试！")
            self.cancel_task(token, claim_id)
        else:
            logger.warning(f"异常的提交任务返回值: \n{response_data}")

        self.mongo.write("task_log", {
            "hotel_name": task_info["hotel_name"],
            "check_in": task_info["check_in"],
            "check_out": task_info["check_out"],
            "status": result,
            "response": json.dumps(response_data)
        })
        return response_data

    def cancel_task(self, token, claim_id, reason_type="搜索不到酒店"):
        """
        取消任务

        Args:
            token (str): 认证token
            claim_id (int): 任务声明ID
            reason_type (str): 取消原因类型，默认为"搜索不到酒店"

        Returns:
            dict: 服务器响应数据
        """
        # URL编码取消原因
        encoded_reason = quote(reason_type, encoding='utf-8')

        url = f"http://47.101.140.209/crowd/task/cancelTask?claimId={claim_id}&reasonType={encoded_reason}&token={token}"

        headers = {
          'Accept': '*/*',
          'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
          'Connection': 'keep-alive',
          'Referer': 'http://47.101.140.209/crowd.html',
          'User-Agent': 'Mozilla/5.0 (Linux; Android 8.0.0; SM-G955U Build/R16NW) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 Edg/142.0.0.0',
          'Cookie': 'crowd-code=759528'
        }

        # 发送GET请求
        resp = requests.get(
            url,
            headers=headers,
            verify=False
        )

        resp.raise_for_status()
        response_data = resp.json()

        if response_data and response_data.get("msg") == '正常返回':
            logger.info("✅ 任务取消成功")
            return response_data
        else:
            error_msg = response_data.get("msg", "未知错误")
            raise Exception(f"任务取消失败: {error_msg}")

    def run(self):
        """单账号运行逻辑 - 支持305错误取消任务"""
        with self.lock:
            self.login()

            while True:
                # 获取任务
                tasks = self.get_running_task() or self.get_tasks()

                if not tasks:
                    logger.info(f"[{self.username}] 当前无可用任务，程序休眠2s")
                    time.sleep(2)
                    continue

                # 接取任务
                task_info = {}
                for task in tasks:
                    task_info = self.task_fetcher(task)
                    if task_info:
                        break

                if not task_info:
                    logger.info(f"[{self.username}] 当前无可用任务，程序休眠2s")
                    time.sleep(2)
                    continue

                claim_id = task_info["claim_id"]
                hotel_name = task_info["hotel_name"]
                if not hotel_name:
                    continue

                logger.info(f"[{self.username}] 》》》》》step2. 酒店：{hotel_name}开始运行\n\n")

                # 改进的重试逻辑，支持305错误处理
                retry_count = 0
                success_response = None
                need_cancel = False

                while retry_count < MAX_RETRIES:
                    response = self.send_task(task_info)

                    # 检查是否是305错误
                    if response and response.get("code") == 305:
                        logger.warning(f"✅ 检测到305错误，准备取消任务")
                        need_cancel = True
                        break

                    # 正常成功判断
                    if response and self.is_valid_response(response, task_info["task_type"]):
                        success_response = response
                        logger.info(f"✅ 第{retry_count + 1}次尝试成功获取有效数据")
                        break
                    else:
                        retry_count += 1
                        if retry_count < MAX_RETRIES:
                            logger.info(f"[{self.username}] 》》》》》 酒店：{hotel_name}重试第{retry_count}次\n\n")
                            time.sleep(5)
                        else:
                            logger.warning(f"❌ 酒店：{hotel_name}重试{MAX_RETRIES}次均失败")

                # 根据结果决定后续操作
                if need_cancel:
                    # 305错误，取消任务
                    logger.warning(f"❌ 酒店：{hotel_name} 遇到305错误，取消任务")
                    self.cancel_task(self.token, claim_id, "携程服务器异常")
                    logger.info(f"[{self.username}] " + "*" * 50)

                elif success_response:
                    logger.info(f"[{self.username}] 》》》》》step3. {hotel_name} 数据请求成功\n\n")

                    try:
                        # 生成截图
                        room_info = self.screenshot(task_info, success_response)
                        logger.info(f"[{self.username}] 》》》》》step4. {hotel_name} 截图成功\n\n")

                        # 图片上传和提交任务
                        submit_map = self.upload_screenshots(room_info)
                        logger.info(f"[{self.username}] 》》》》》step5. {hotel_name} 图片上传成功\n\n")

                        # 提交任务
                        self.submit_template_task(task_info, self.token, submit_map, claim_id)
                        logger.info(f"[{self.username}] " + "*" * 50)

                    except Exception as e:
                        logger.error(f"❌ 任务后续处理失败: {e}")
                        self.cancel_task(self.token, claim_id, "处理失败")
                else:
                    # 重试次数用尽，取消任务
                    logger.warning(f"❌ 酒店：{hotel_name} 数据获取失败，取消任务")
                    self.cancel_task(self.token, claim_id, "数据获取失败")

    def is_valid_response(self, response: dict, task_type: str) -> bool:
        """判断响应是否有效（排除305错误）"""
        if not response:
            return False

        if response.get("error") == "timeout":
            return False

        # 排除305错误
        if response.get("code") == 305:
            return False

        if task_type == "XC_ROOM_DETAIL_RP_PIC_DISCOUNT":
            return bool(response.get("data"))
        else:
            return response.get('code') == 305 or bool(response.get("data"))

    def upload_screenshots(self, room_info):
        """提取截图上传逻辑"""
        submit_map = {}
        for item in room_info:
            key = item["key"]
            image_paths = item["screenshots"]
            submit_map[key] = []

            for img_path in image_paths:
                file_name = os.path.basename(img_path)
                oss_info = self.get_oss_upload_info(self.token, file_name)
                self.upload_to_oss(img_path, oss_info)
                submit_map[key].append(oss_info["ossKey"])
                time.sleep(0.5)

        return submit_map

class MultiAccountScheduler:
    """
    多账号并发调度器
    """

    def __init__(self, accounts: List[Dict[str, str]]):
        """
        Args:
            accounts: 账号列表，格式 [{"username": "user1", "password": "pwd1"}, ...]
        """
        self.accounts = accounts
        self.schedulers = []
        self._init_schedulers()

    def _init_schedulers(self):
        """初始化每个账号的调度器"""
        for account in self.accounts:
            scheduler = SchedulerAuto(
                username=account["username"],
                password=account["password"]
            )
            self.schedulers.append(scheduler)

    def run_sequential(self):
        """顺序执行（用于调试）"""
        for i, scheduler in enumerate(self.schedulers):
            logger.info(f"开始执行第 {i + 1} 个账号: {scheduler.username}")
            try:
                scheduler.run()
            except Exception as e:
                logger.error(f"账号 {scheduler.username} 执行失败: {e}")

    def run_concurrent(self, max_workers: int = None):
        """
        并发执行多账号

        Args:
            max_workers: 最大并发数，默认使用账号数量
        """
        if max_workers is None:
            max_workers = len(self.schedulers)

        logger.info(f"开始并发执行 {len(self.schedulers)} 个账号，最大并发数: {max_workers}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_scheduler = {
                executor.submit(self._run_scheduler_wrapper, scheduler): scheduler
                for scheduler in self.schedulers
            }

            # 等待所有任务完成
            for future in concurrent.futures.as_completed(future_to_scheduler):
                scheduler = future_to_scheduler[future]
                try:
                    future.result()
                    logger.info(f"账号 {scheduler.username} 执行完成")
                except Exception as e:
                    logger.error(f"账号 {scheduler.username} 执行失败: {e}")

    def _run_scheduler_wrapper(self, scheduler):
        """包装执行函数，添加异常处理"""
        scheduler.run()

    def run_continuous(self, max_workers: int = None):
        """
        持续并发运行（推荐使用）
        每个账号在自己的线程中持续运行
        """
        if max_workers is None:
            max_workers = len(self.schedulers)

        logger.info(f"启动持续并发执行，账号数: {len(self.schedulers)}，并发数: {max_workers}")

        # 使用线程池管理所有账号的持续运行
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 为每个调度器提交持续运行任务
            futures = [
                executor.submit(self._run_continuous_wrapper, scheduler)
                for scheduler in self.schedulers
            ]

            # 等待所有任务（实际上会持续运行直到手动停止）
            try:
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"账号执行异常: {e}")
            except KeyboardInterrupt:
                logger.info("收到中断信号，停止所有任务")
                for future in futures:
                    future.cancel()

    def _run_continuous_wrapper(self, scheduler):
        """持续运行包装器，包含重启逻辑"""
        while True:
            try:
                logger.info(f"启动账号 {scheduler.username} 的任务执行")
                scheduler.run()
            except Exception as e:
                logger.error(f"账号 {scheduler.username} 执行异常，10秒后重启: {e}")
                time.sleep(10)

def start_multi_account_scheduler():
    """启动多账号调度器"""
    logger.info(f"🚀 定时任务触发，启动多账号调度器 - {datetime.datetime.now()}")

    accounts = [
        {"username": "sx001", "password": "759528"},
        {"username": "sx002", "password": "605236"},
        {"username": "sx003", "password": "575993"},
        {"username": "sx004", "password": "538615"},

        {"username": "sx005", "password": "964202"},
        {"username": "sx006", "password": "855541"},
        {"username": "sx007", "password": "967291"},
        {"username": "sx008", "password": "902115"},
        {"username": "sx009", "password": "736374"},
        {"username": "sx010", "password": "993014"},
        #
        # {"username": "sx61", "password": "741088"},
        # {"username": "sx62", "password": "039942"},
        # {"username": "sx63", "password": "403912"},
        # {"username": "sx64", "password": "161184"},
        # {"username": "sx65", "password": "589375"},
        # {"username": "sx66", "password": "573116"},
        # {"username": "sx67", "password": "667003"},
        # {"username": "sx68", "password": "400844"},
        # {"username": "sx69", "password": "977866"},
        # {"username": "sx70", "password": "574024"},
    ]

    # 创建多账号调度器并执行
    multi_scheduler = MultiAccountScheduler(accounts)
    multi_scheduler.run_concurrent()

if __name__ == '__main__':
    # # 1️⃣ 你的 token（示例中从 curl 提取）
    # 创建调度器
    # scheduler = BlockingScheduler()
    #
    # # 添加定时任务：每天8点执行
    # scheduler.add_job(
    #     start_multi_account_scheduler,
    #     trigger=CronTrigger(hour=8, minute=00),
    #     id='daily_multi_account_task'
    # )
    #
    # logger.info("✅ 定时任务设置完成：每天08:00自动启动")
    #
    # try:
    #     # 启动调度器
    #     scheduler.start()
    # except KeyboardInterrupt:
    #     logger.info("🛑 收到中断信号，停止调度器")
    # except Exception as e:
    #     logger.error(f"调度器异常: {e}")
    start_multi_account_scheduler()