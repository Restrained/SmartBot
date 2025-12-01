# scheduler_auto_refactor.py
import json
import time
import uuid
import logging
import threading
import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 假定这些是你项目里已有的单例/工厂函数
# from db.mongo import MongoClientSingleton
# from scheduler import REDIS_HOST, REDIS_PORT, REDIS_DB
# 我这里用占位
from redis import Redis

# -----------------------------------------------------------------------------
# 配置 / 常量
# -----------------------------------------------------------------------------
logger = logging.getLogger("scheduler_auto")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

MAX_RETRIES = 4
DEFAULT_TIMEOUT = 10  # seconds for http requests
BASE_URL = "http://47.101.140.209/crowd"

# -----------------------------------------------------------------------------
# 小型数据结构
# -----------------------------------------------------------------------------
@dataclass
class TaskInfo:
    city: str = ""
    hotel_name: str = ""
    claim_id: str = ""
    check_in: str = ""
    check_out: str = ""
    task_type: str = ""
    room_info: List[Dict[str, Any]] = None

    def to_dict(self):
        return asdict(self)

# -----------------------------------------------------------------------------
# Http client wrapper with retries and session
# -----------------------------------------------------------------------------
class HttpClient:
    def __init__(self, base_url: str = BASE_URL, timeout: int = DEFAULT_TIMEOUT, verify: bool = True):
        self.base_url = base_url.rstrip("/")
        self.verify = verify
        self.timeout = timeout
        self.session = requests.Session()
        # 默认 headers，可以在外部替换
        self.session.headers.update({
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json"
        })
        retries = Retry(total=3, backoff_factor=0.5,
                        status_forcelist=[429, 500, 502, 503, 504],
                        allowed_methods=["GET", "POST"])
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def post(self, path: str, json_data: dict = None, params: dict = None, headers: dict = None, cookies: dict = None, timeout: Optional[int] = None):
        url = f"{self.base_url}{path}"
        timeout = timeout or self.timeout
        resp = self.session.post(url, json=json_data, params=params, headers=headers, cookies=cookies, timeout=timeout, verify=self.verify)
        return resp

    def get(self, path: str, params: dict = None, headers: dict = None, timeout: Optional[int] = None):
        url = f"{self.base_url}{path}"
        timeout = timeout or self.timeout
        resp = self.session.get(url, params=params, headers=headers, timeout=timeout, verify=self.verify)
        return resp

# -----------------------------------------------------------------------------
# Login manager
# -----------------------------------------------------------------------------
class LoginManager:
    def __init__(self, http: HttpClient, username: str, password: str):
        self.http = http
        self.username = username
        self.password = password
        self.token: Optional[str] = None

    def rsa_encrypt_base64(self, content: str) -> str:
        # TODO: 使用你项目中的 rsa_encrypt_base64
        # 这里我假设函数存在于外部模块；若没有，请替换为正确实现
        return content

    def login(self) -> Optional[str]:
        api_path = "/task/login"
        payload = self.rsa_encrypt_base64(f"{self.username}_{self.password}")
        # note: 原始你传 body 但没有指定是 json/data；这里我们传 json 字段则服务器需要支持
        try:
            resp = self.http.post(api_path, json_data=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get("success") and data.get("code") == 200:
                self.token = data.get("data")
                logger.info(f"登录成功: {self.username}")
                return self.token
            else:
                logger.warning(f"登录失败: {data.get('msg')}")
        except Exception as e:
            logger.error(f"登录异常: {e}")
        return None

# -----------------------------------------------------------------------------
# TaskManager: 获取/过滤/领取/取消任务
# -----------------------------------------------------------------------------
class TaskManager:
    def __init__(self, http: HttpClient, token_getter: callable):
        """
        token_getter: function that returns current token string
        """
        self.http = http
        self.get_token = token_getter

    def get_tasks(self) -> List[Dict]:
        path = "/task/listTask"
        token = self.get_token()
        if not token:
            logger.warning("token 未设置，无法获取任务")
            return []
        try:
            resp = self.http.get(path, params={"token": token})
            resp.raise_for_status()
            data = resp.json()
            tasks = data.get("data", [])
            return tasks
        except Exception as e:
            logger.warning(f"获取任务出错: {e}")
            return []

    def task_filter(self, raw_tasks: Dict) -> List[Dict]:
        result = []
        data = raw_tasks.get("data", []) if isinstance(raw_tasks, dict) else raw_tasks
        for item in data:
            try:
                task_site = item.get("taskSite")
                biz_type = item.get("bizType")
                valid_task_num = item.get("validTaskNum", 0)
                task_name = item.get("taskName", "")
                day_task_num_limit = int(item.get("dayTaskNumLimit") or 0)
                claim_task_num = int(item.get("claimTaskNum") or 0)
                if all([
                    claim_task_num < day_task_num_limit,
                    task_site == "XC",
                    biz_type == "HOTEL",
                    valid_task_num > 0,
                    "国内" in task_name,
                    item.get("taskType") == "XC_ROOM_DETAIL_RP_PIC_DISCOUNT"
                ]):
                    result.append({
                        "task_id": item["id"],
                        "task_name": task_name,
                        "task_type": item["taskType"],
                        "valid_task_num": valid_task_num,
                    })
            except Exception:
                logger.exception("过滤任务时出现异常，跳过该条")
        if not result:
            logger.warning("当前账号无可领任务")
        return result

    def fetch_task(self, original_task_info: dict, running_task=False) -> TaskInfo:
        api = "/task/queryClaimTemplateTask" if running_task else "/task/claimTemplateTask"
        token = self.get_token()
        params = {"taskSetId": original_task_info["task_id"], "token": token}
        try:
            resp = self.http.get(api, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 200 and data.get("msg") == "正常返回":
                d = data["data"]
                task_info = TaskInfo()
                task_info.claim_id = d.get("claimId")
                # parse taskInfo
                for item in d.get("taskInfo", []):
                    label = item.get("label", "")
                    if label == "所在城市":
                        task_info.city = item.get("value") or ""
                    elif label == "酒店名称":
                        task_info.hotel_name = item.get("value") or ""
                # parse task group / dates / rooms
                task_group = d.get("taskGroup", [])
                if task_group:
                    group0 = task_group[0]
                    title = group0.get("title", "")
                    if "离店时间" in title:
                        task_info.check_in, task_info.check_out = SchedulerUtils.extract_dates(title)
                    task_list = group0.get("taskList", [])
                    rooms = []
                    for item in task_list:
                        key = item.get("key")
                        raw_title = item.get("title", "")
                        if raw_title == "列表页信息":
                            room_name = raw_title
                        else:
                            room_name = SchedulerUtils.extract_room_name(raw_title)
                        rooms.append({"key": key, "title": room_name})
                    task_info.room_info = rooms
                return task_info
            elif data.get("msg") == "当日无待领取任务":
                return TaskInfo()
        except Exception as e:
            logger.error(f"领取任务异常: {e}")
        return TaskInfo()

    def cancel_task(self, token: str, claim_id: str, reason_type: str = "搜索不到酒店") -> Dict:
        encoded_reason = quote(reason_type, encoding="utf-8")
        path = f"/task/cancelTask?claimId={claim_id}&reasonType={encoded_reason}&token={token}"
        try:
            resp = self.http.get(path)
            resp.raise_for_status()
            data = resp.json()
            if data.get("msg") == "正常返回":
                logger.info("取消任务成功")
                return data
            else:
                raise Exception(f"取消任务失败: {data.get('msg')}")
        except Exception as e:
            logger.error(f"取消任务请求失败: {e}")
            return {"err": str(e)}

# -----------------------------------------------------------------------------
# Screenshot manager: render html via flask endpoint + playwright
# -----------------------------------------------------------------------------
class ScreenshotManager:
    def __init__(self, flask_render_url: str = "http://127.0.0.1:5000/render_room"):
        self.flask_render_url = flask_render_url
        # TODO: 你可在这里注入 playwright 的配置

    def parse_and_render(self, hotel_name: str, check_in: str, check_out: str, rooms: List[Dict], dialogs: List[Dict]) -> str:
        """调用 Flask 渲染，返回 HTML 文本"""
        payload = {
            "hotel_name": hotel_name,
            "checkin_date": check_in,
            "checkout_date": check_out,
            "stay_night": 1,
            "rooms": rooms,
            "dialog": dialogs
        }
        r = requests.post(self.flask_render_url, json=payload, timeout=20)
        r.raise_for_status()
        return r.text

    def capture_all(self, task_info: TaskInfo, parsed_response: dict) -> List[Dict]:
        """
        parsed_response: 你的 get_task_result() 返回的结构（已经是 dict）
        返回值：room_info_list，格式与原来相同但 screenshots 字段填充为本地路径列表
        """
        import os
        from playwright.sync_api import sync_playwright

        # 准备输出目录
        today = datetime.datetime.now().strftime("%Y%m%d")
        out_dir = Path(f"screenshots/{today}/{task_info.hotel_name}")
        out_dir.mkdir(parents=True, exist_ok=True)

        # TODO: 解析 parsed_response 成 rooms / dialogs
        rooms, dialogs = SchedulerUtils.parse_room(parsed_response)  # 你需要在 SchedulerUtils 中实现 parse_room
        room_info_list = task_info.room_info or []
        for r in room_info_list:
            r["screenshots"] = []

        html_cache = {}
        # 启动浏览器
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(**pw.devices.get("iPhone X", {}))
            page = context.new_page()
            self._patch_page(page)

            # 首先渲染一次整体页面（如果每个房型需要不同数据可针对每次渲染）
            # 下面我们为每个房型单独 render（与原逻辑类似）
            for room_item in room_info_list:
                title = room_item["title"].strip()
                if title == "列表页信息":
                    continue
                # 匹配房型
                target_rooms = [r for r in rooms if title == (r.get("name") or "")]
                if not target_rooms:
                    logger.warning(f"未匹配到房型：{title}")
                    continue
                breakfast_map = SchedulerUtils.compute_breakfast_lowest_variant(target_rooms)
                matched_dialogs = [
                    d for d in dialogs
                    if d.get("room_code") and any(v.get("code") == d.get("room_code") for v in breakfast_map.values())
                ]
                payload_rooms = list(breakfast_map.values())
                # 渲染 HTML
                html = self.parse_and_render(task_info.hotel_name, task_info.check_in, task_info.check_out, payload_rooms, matched_dialogs)
                page.set_content(html, wait_until="networkidle")
                time.sleep(0.2)
                # 列表页截图（单张）
                list_img = out_dir / f"{uuid.uuid4().hex}_list.png"
                page.screenshot(path=str(list_img))
                logger.info(f"列表页截图: {list_img}")
                # 保存到对应的 列表页对象（找到 '列表页信息'）
                list_page_item = next((i for i in room_info_list if i["title"] == "列表页信息"), None)
                if list_page_item:
                    list_page_item.setdefault("screenshots", []).append(str(list_img))

                # 弹窗截图
                for b_type, variant in breakfast_map.items():
                    variant_code = variant.get("code")
                    dialog_selector_btn = f'.open-discount-btn[data-dialog-id="dialog-{variant_code}"]'
                    btn = page.query_selector(dialog_selector_btn)
                    if not btn:
                        logger.warning(f"未找到弹窗按钮: {dialog_selector_btn}")
                        continue
                    try:
                        btn.scroll_into_view_if_needed()
                        page.wait_for_timeout(200)
                        btn.click()
                        page.wait_for_timeout(600)
                        dialog_img = out_dir / f"{uuid.uuid4().hex}_dialog.png"
                        page.screenshot(path=str(dialog_img))
                        logger.info(f"弹窗截图: {dialog_img}")
                        room_item.setdefault("screenshots", []).append(str(dialog_img))
                        # 关闭弹窗：优先尝试选择 .close[data-dialog-id="dialog-{code}"]
                        SchedulerUtils.safe_close_dialog_on_page(page, variant_code)
                    except Exception as e:
                        logger.exception(f"弹窗截图异常: {e}")

            browser.close()
        return room_info_list

    def _patch_page(self, page):
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

# -----------------------------------------------------------------------------
# OSS uploader
# -----------------------------------------------------------------------------
class OssUploader:
    def __init__(self, http: HttpClient):
        self.http = http

    def get_oss_info(self, token: str, file_name: str) -> dict:
        path = "/task/getOssKey"
        payload = {"bizType": "HOTEL", "fileName": file_name, "token": token}
        # 这里使用 base url + path which will be http://47.101.140.209/crowd/task/getOssKey
        try:
            resp = self.http.post(path, json_data=payload, cookies={"crowd-code": "759528"})
            resp.raise_for_status()
            data = resp.json()
            if data.get("msg") == "正常返回":
                logger.info("获取 OSS 上传参数成功")
                return data["data"]
        except Exception as e:
            logger.warning(f"获取 OSS 参数失败: {e}")
        raise RuntimeError("获取 OSS 参数失败")

    def upload_file(self, file_path: str, oss_info: dict):
        url = f"https://{oss_info['url']}/"
        # 注意：每个 OSS 服务表单字段可能不同。根据你后端返回的字段调整
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
        # 使用 with open 保证文件被关闭
        with open(file_path, "rb") as f:
            files = {"file": (Path(file_path).name, f, "image/png")}
            # 这里不走 HttpClient（因为是外部 OSS），用 requests 直接发
            resp = requests.post(url, data=data, files=files, timeout=30)
            if resp.status_code in (200, 201, 204):
                logger.info("上传到 OSS 成功")
                return True
            logger.warning(f"上传 OSS 返回: {resp.status_code} {resp.text}")
            return False

# -----------------------------------------------------------------------------
# Utils: 日期解析、房型解析 等
# -----------------------------------------------------------------------------
import re
class SchedulerUtils:
    @staticmethod
    def extract_dates(text: str) -> Tuple[Optional[str], Optional[str]]:
        pattern = r"店时间[:：]?\s*(\d{4}-\d{2}-\d{2}).*?离店时间[:：]?\s*(\d{4}-\d{2}-\d{2})"
        m = re.search(pattern, text)
        if m:
            return m.group(1), m.group(2)
        return None, None

    @staticmethod
    def extract_room_name(raw: str) -> str:
        # 尝试多种常见分隔符
        m = re.search(r'房型[:：]\s*(.*?)\s*(?:\n|$)', raw)
        if m:
            return m.group(1).strip()
        # 兜底：返回原始文本的首行（更稳健）
        return raw.splitlines()[0].strip()

    @staticmethod
    def parse_room(response: dict) -> Tuple[List[dict], List[dict]]:
        """
        TODO: 你原始的 parse_room 逻辑在别处，确保这里实现能够根据 response 返回 rooms, dialogs
        这里仅给示例格式。
        """
        rooms = response.get("rooms", []) if isinstance(response, dict) else []
        dialogs = response.get("dialogs", []) if isinstance(response, dict) else []
        return rooms, dialogs

    @staticmethod
    def compute_breakfast_lowest_variant(rooms: List[dict]) -> Dict[str, dict]:
        breakfast_types = ["无早餐", "1份早餐", "2份早餐"]
        result = {}
        for room in rooms:
            bf_raw = room.get("breakfast", "") or ""
            matched = next((b for b in breakfast_types if b in bf_raw), "无早餐")
            price_raw = room.get("price", None)
            try:
                price = float(price_raw) if price_raw is not None else float("inf")
            except Exception:
                price = float("inf")
            if matched not in result or price < float(result[matched].get("price", float("inf"))):
                result[matched] = room
        return result

    @staticmethod
    def safe_close_dialog_on_page(page, variant_code: str):
        try:
            close_sel = f'.close[data-dialog-id="dialog-{variant_code}"]'
            btn = page.query_selector(close_sel)
            if btn:
                btn.scroll_into_view_if_needed()
                btn.click()
            else:
                mask_sel = f"#mask-{variant_code}"
                mask = page.query_selector(mask_sel)
                if mask:
                    mask.click()
                else:
                    page.mouse.click(10, 10)
            page.wait_for_timeout(200)
        except Exception:
            try:
                page.mouse.click(10, 10)
            except Exception:
                pass

# -----------------------------------------------------------------------------
# SchedulerAuto orchestrator (原 SchedulerAuto 的 refactor)
# -----------------------------------------------------------------------------
class SchedulerAuto:
    def __init__(self, username: str, password: str, redis_host="localhost"):
        self.username = username
        self.password = password
        self.lock = threading.Lock()
        self.http = HttpClient(base_url=BASE_URL, timeout=DEFAULT_TIMEOUT, verify=False)  # verify False 保持原来行为
        self.login_mgr = LoginManager(self.http, username, password)
        self.task_mgr = TaskManager(self.http, lambda: self.login_mgr.token)
        self.screenshot_mgr = ScreenshotManager()
        self.oss_uploader = OssUploader(self.http)
        # Replace with your actual Mongo/Redis singletons
        self.redis = Redis(host=redis_host)
        # self.mongo = MongoClientSingleton(db_name="ctrip")
        self.mongo = None  # TODO: 注入你的 Mongo 单例

    def run_once(self):
        """处理一次循环（便于单元测试与调度）"""
        with self.lock:
            token = self.login_mgr.login()
            if not token:
                logger.warning("登录失败，退出本次循环")
                return

            # 先检查运行中任务
            running = self.get_running_task()
            tasks = running or self.task_mgr.get_tasks()
            tasks = self.task_mgr.task_filter({"data": tasks}) if tasks else []
            if not tasks:
                logger.info("当前无可用任务")
                return

            selected_task = None
            for t in tasks:
                info = self.task_mgr.fetch_task(t, running_task=bool(running))
                if info and info.hotel_name:
                    selected_task = info
                    break

            if not selected_task:
                logger.info("未获取到可执行任务")
                return

            logger.info(f"开始处理任务: {selected_task.hotel_name}")
            # 1) 发送任务到队列（替代原逻辑）
            response = self.send_task_and_wait(selected_task)
            if not response:
                logger.warning("任务请求失败/超时，取消任务")
                self.task_mgr.cancel_task(token, selected_task.claim_id)
                return

            # 2) 截图
            room_info = self.screenshot_mgr.capture_all(selected_task, response)
            # 3) 上传并提交
            submit_map = {}
            for item in room_info:
                k = item["key"]
                submit_map[k] = []
                for img in item.get("screenshots", []):
                    fname = Path(img).name
                    oss_info = self.oss_uploader.get_oss_info(token, fname)
                    success = self.oss_uploader.upload_file(img, oss_info)
                    if success:
                        submit_map[k].append(oss_info["ossKey"])
                    else:
                        logger.warning(f"上传失败: {img}")

            # 4) 提交任务
            self.submit_template_task(selected_task, token, submit_map, selected_task.claim_id)

    def get_running_task(self) -> List[Dict]:
        api = "/task/queryClaimRecordList"
        params = {"type": "today", "claimStatus": "CLAIMED", "pageSize": "10", "pageNo": "1", "token": self.login_mgr.token}
        try:
            resp = self.http.get(api, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 200 and data.get("msg") == "正常返回":
                d = data.get("data") or {}
                task_list = d.get("claimRecordVOList", [])
                if task_list:
                    item = task_list[0]
                    return [{
                        "task_id": item["taskSetId"],
                        "task_name": item["shidName"],
                        "task_type": item["taskType"],
                        "valid_task_num": 1,
                        "running_task": 1
                    }]
        except Exception as e:
            logger.error(f"获取运行中任务异常: {e}")
        return []

    def send_task_and_wait(self, task_info: TaskInfo, collection: str = "ctrip_detail_results", timeout: int = 300):
        """
        把任务推送入队并轮询 mongo/redis 获取结果（与原来 send_task 逻辑类似）
        这里示例化一个简略流程：直接调用外部系统并等待结果
        """
        # 1. 投放到 redis set（保留原语义）
        queue_name = "ctrip_detail_queue" if task_info.task_type == "XC_ROOM_DETAIL_RP_PIC_DISCOUNT" else "ctrip_list_queue"
        self.redis.sadd(queue_name, json.dumps(task_info.to_dict()))
        logger.info(f"已将任务放入队列 {queue_name}")

        # 等待结果（轮询 mongo）
        start = time.time()
        while time.time() - start < timeout:
            res = self.get_task_result(task_info, collection)
            ok, parsed = self.handle_task_result(res, task_info.task_type)
            if ok:
                return parsed
            time.sleep(3)
        logger.warning("等待任务结果超时")
        return None

    def get_task_result(self, task_info: TaskInfo, collection: str):
        """
        读取 mongo（或 redis）以获取任务结果（示例化）
        你需要把 self.mongo 设置成真正的 Mongo 客户端实例
        """
        if not self.mongo:
            logger.warning("未注入 mongo 实例，无法查询结果")
            return {}
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        query = {"hotel_name": task_info.hotel_name, "check_in": task_info.check_in, "check_out": task_info.check_out, "date": today}
        result = self.mongo.find_one(collection, query=query)
        if result:
            return json.loads(result.get("response", "{}"))
        return {}

    def handle_task_result(self, result: dict, task_type: str) -> Tuple[bool, dict]:
        s = json.dumps(result or {})
        if "priceInfo" in s and task_type == "XC_ROOM_DETAIL_RP_PIC_DISCOUNT" and "totalPriceInfo" in s:
            return True, result
        if task_type != "XC_ROOM_DETAIL_RP_PIC_DISCOUNT" and ("tipAfterPrice" in s or "酒店已售罄" in s):
            return True, result
        return False, {}

    def submit_template_task(self, task_info: TaskInfo, token: str, submit_task_map: Dict[str, List[str]], claim_id: str, do_submit: bool = True):
        path = f"/task/submitTemplateTask?token={token}"
        payload = {
            "claimId": claim_id,
            "giveUpTaskMap": "{}",
            "submitTaskMap": json.dumps(submit_task_map, ensure_ascii=False),
            "doSubmit": do_submit,
            "token": token
        }
        try:
            resp = self.http.post(path, json_data=payload)
            resp.raise_for_status()
            data = resp.json()
            result = "Failure"
            if data.get("msg") == '未识别到匹配房型，请重试！':
                logger.warning("模板任务提交失败，已取消任务")
                self.task_mgr.cancel_task(token, claim_id)
            elif data.get("msg") == "正常返回":
                logger.info(f"{task_info.hotel_name} 提交成功")
                result = "Success"
            elif data.get("msg") in ('任务集已失效，请刷新后重试', '找不到该任务认领记录'):
                logger.info("任务已失效或找不到认领记录，取消")
                self.task_mgr.cancel_task(token, claim_id)
            else:
                logger.warning(f"提交返回异常: {data}")
            # 写日志到 mongo（如果存在）
            try:
                if self.mongo:
                    self.mongo.write("task_log", {
                        "hotel_name": task_info.hotel_name,
                        "check_in": task_info.check_in,
                        "check_out": task_info.check_out,
                        "status": result,
                        "response": json.dumps(data, ensure_ascii=False)
                    })
            except Exception:
                logger.exception("写 task_log 到 mongo 失败")
            return data
        except Exception as e:
            logger.exception(f"提交模板任务异常: {e}")
            return {"err": str(e)}

# -----------------------------------------------------------------------------
# Example usage
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # 示例：如何用
    s = SchedulerAuto("your_username", "your_password", redis_host="127.0.0.1")
    # 注入 mongo 单例（如果有）
    # s.mongo = MongoClientSingleton(db_name="ctrip")
    # 运行一次（建议放到循环或调度器里，原来你的 run() 是长循环，这里不再自动循环）
    s.run_once()
