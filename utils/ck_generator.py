import time
import redis
import requests
from playwright.sync_api import sync_playwright
from loguru import logger

from scheduler import REDIS_HOST, REDIS_PORT, REDIS_DB

# ====== 配置 ======
URL = "https://accounts.ctrip.com/h5Login/login_ctrip?sibling=T"
STORAGE_STATE = "ctrip_storage_state.json"


COOKIE_HASH = "ctrip_ck_hash"
COOKIE_READY = "ctrip_ck"
COOKIE_COOLDOWN = "ctrip_ck_cooldown"
COOKIE_POOL_SIZE = 2  # Cookie 池阈值

# ====== 接口手机号平台类 ======
class PhonePlatform:
    def __init__(self):
        self.host = "54.178.12.32:8000"
        self.username = "stxc"
        self.password = "f613"
        self.product_id = "236"
        self.token = None
        self.phone_number = None

    def request(self, url, params, method="get", data=None):
        try:
            if method == "get":
                return requests.get(url, params=params, timeout=10)
            else:
                return requests.post(url, data=data, params=params, timeout=10)
        except Exception as e:
            logger.error(f"请求异常: {e}")
            return None

    def is_success(self, resp):
        return resp and resp.status_code == 200 and resp.json().get("code") == 200

    def login(self):
        api = f"http://{self.host}/api/user/apiLogin"
        params = {"username": self.username, "password": self.password}
        resp = self.request(api, params)
        if self.is_success(resp):
            self.token = resp.json()["result"]["token"]
            logger.info("✅ 登录手机号平台成功")
        else:
            logger.error("手机号平台登录失败")
        return self.token

    def get_phone_number(self):
        api = f"http://{self.host}/api/phone/getPhone"
        params = {
            "productId": self.product_id,
            "username": self.username,
            "token": self.token,
        }
        resp = self.request(api, params)
        if self.is_success(resp):
            self.phone_number = resp.json()["result"]["phones"]
            logger.info(f"📞 获取号码成功: {self.phone_number}")
            return self.phone_number
        logger.error("获取手机号失败")
        return None

    def get_verify_code(self):
        api = f"http://{self.host}/api/phone/getCode"
        params = {
            "productId": self.product_id,
            "username": self.username,
            "phone": self.phone_number,
            "token": self.token,
        }
        start = time.time()
        timeout = 60
        interval = 3
        while time.time() - start < timeout:
            resp = self.request(api, params)
            if self.is_success(resp):
                result = resp.json().get("result", {})
                if result.get("status") == 1:
                    code = result.get("code")
                    logger.info(f"✅ 验证码获取成功: {code}")
                    self.feedback_status(1)
                    return code
                else:
                    logger.info("⏳ 验证码未生成，等待3秒...")
            time.sleep(interval)
        logger.warning("⚠️ 验证码获取超时")
        self.feedback_status(2)
        return None

    def feedback_status(self, result: int):
        api = f"http://{self.host}/api/phone/reportResult"
        params = {
            "productId": self.product_id,
            "username": self.username,
            "token": self.token,
            "result": result,
            "phone": self.phone_number,
        }
        while True:
            resp = self.request(api, params)
            if self.is_success(resp):
                logger.info(f"📤 状态反馈成功 ({result})")
                break
            elif "反馈过快" in resp.text:
                time.sleep(10)
            else:
                logger.info(resp.text)
                logger.warning("反馈失败")
                break

# ====== Redis 工具 ======
def get_cookie_count():
    r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    ready_count = r.scard(COOKIE_READY)  # 可用 cookie 数量
    cooldown_count = r.zcard(COOKIE_COOLDOWN)  # 冷却中的 cookie 数量
    return ready_count + cooldown_count
  

def save_cookie_to_redis(cookies, phone_number):
    r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    r.hset(COOKIE_HASH, phone_number, cookie_str)
    r.sadd(COOKIE_READY, cookie_str)
    logger.success(f"✅ 写入 Redis -> {COOKIE_HASH} field={phone_number}")
    return cookie_str

# ====== Playwright 登录部分 ======
# 推荐的手机号输入和按钮选择器（按需调整）
USERNAME_SELECTORS = [
    'input[type="tel"]',
    'input[placeholder*="手机号"]',
    'input[placeholder*="输入手机号"]',
]
SEND_CODE_SELECTORS = [
    'a:has-text("获取验证码")',
    'button:has-text("获取验证码")',
    'button:has-text("发送验证码")',
]
VERIFICATION_INPUT_SELECTORS = [
    'input[placeholder*="验证码"]',
    'input[type="text"][aria-label*="verify"]',
]
SWITCH_TO_CODE_LOGIN_SELECTORS = [
    'button:has-text("手机验证码登录")',
    'button:has-text("短信登录")',
]
LOGIN_BUTTON_SELECTORS = [
    "button:has-text('登录')",
    "button:has-text('登 录')",
]

def _try_fill_input(page, selectors, value):
    for sel in selectors:
        try:
            locator = page.locator(sel)
            if locator.count() and locator.first.is_visible():
                locator.first.fill(value)
                return sel
        except Exception:
            continue
    return None

def _try_click(page, selectors):
    for sel in selectors:
        try:
            locator = page.locator(sel)
            if locator.count() and locator.first.is_visible():
                locator.first.click()
                return sel
        except Exception:
            continue
    return None

def record_phone_usage(phone: str):
    """记录手机号获取次数，用于检测是否重复发号"""
    try:
        r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        key = "ctrip_phone_stat"
        # 每次获取新手机号就自增计数
        count = r.hincrby(key, phone, 1)
        logger.info(f"📱 号码 {phone} 已获取 {count} 次")
    except Exception as e:
        logger.error(f"记录手机号使用次数失败: {e}")

def generate_one_cookie(phone_platform: PhonePlatform, headless=True, max_phone_attempts=None):
    """
    在单个浏览器实例内重复：
      1) 从 phone_platform 获取手机号
      2) 在页面输入并点击「获取验证码」
      3) 调用 phone_platform.get_verify_code() 等待接口返回验证码
      4) 若接口超时返回 None -> 清空手机号输入框，反馈状态已在 get_verify_code 里做（result=2），重新获取手机号重复
      5) 若拿到验证码 -> 输入验证码并登录，保存 cookie -> 关闭浏览器并返回 True
    max_phone_attempts: 如果希望在单浏览器实例内限制尝试次数，可传入整数；None 表示无限次尝试
    返回：True 表示本次成功获取并保存 cookie；False 表示浏览器流程异常未成功（会回到主循环重新开始）
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
            page.goto(URL, wait_until="networkidle")
            # 切换到验证码登录（若存在）
            _try_click(page, SWITCH_TO_CODE_LOGIN_SELECTORS)
            attempts = 0

            while True:
                attempts += 1
                if max_phone_attempts and attempts > max_phone_attempts:
                    logger.warning("达到本浏览器最大尝试次数，放弃此浏览器实例。")
                    break

                # 1) 从接口取号
                phone = phone_platform.get_phone_number()
                if not phone:
                    logger.warning("获取手机号失败，等待 3 秒后重试...")
                    time.sleep(3)
                    continue

                # ✅ 记录手机号使用次数
                record_phone_usage(phone)
                logger.info(f"在页面输入手机号并点击发送验证码：{phone}")

                # 2) 在页面填手机号
                sel_used = _try_fill_input(page, USERNAME_SELECTORS, phone)
                if not sel_used:
                    logger.warning("未找到手机号输入框选择器，尝试通过 JS 清空后继续（兼容性处理）")
                    # 尝试直接用一个常见选择器，再次尝试
                    try:
                        page.fill('input[type="tel"]', phone)
                        sel_used = 'input[type="tel"]'
                    except Exception as e:
                        logger.error("无法填写手机号输入框，终止本浏览器实例。")
                        break

                # 3) 点击发送验证码
                clicked = _try_click(page, SEND_CODE_SELECTORS)
                if not clicked:
                    logger.warning("未能点击到发送验证码按钮，尝试再次点击或等待...")
                    # 尝试等待并再次点击通用选择器
                    try:
                        page.click('a.valid-get-code', timeout=2000)
                        clicked = 'a.valid-get-code'
                    except Exception:
                        logger.error("无法点击发送验证码，放弃此手机号，尝试获取新手机号。")
                        # optional: call phone_platform.feedback_status(2) but get_verify_code will do it on timeout
                        # 清空手机号输入框以便下次填写新号
                        try:
                            if sel_used:
                                page.fill(sel_used, "")
                        except Exception:
                            pass
                        continue

                # 4) 请求接口轮询验证码（get_verify_code 内会等待最多 60s 并在超时时 feedback_status(2)）
                code = phone_platform.get_verify_code()
                if not code:
                    logger.warning("接口未返回验证码（超时或失败）。将在页面清空手机号并重新获取新号码重试。")
                    # 清空页面手机号输入框（使用上次成功填写的选择器）
                    try:
                        if sel_used:
                            page.fill(sel_used, "")
                        else:
                            # 尝试通用清空
                            page.fill('input[type="tel"]', "")
                    except Exception:
                        logger.debug("清空手机号输入框时发生异常（可忽略）")
                    # 接口端已经反馈为无验证码（在 get_verify_code 中），继续循环重新取号
                    time.sleep(1)
                    continue

                # 5) 如果拿到验证码，填写并点击登录
                logger.info(f"收到验证码，准备在页面填写并登录。验证码={code}")
                ver_sel = _try_fill_input(page, VERIFICATION_INPUT_SELECTORS, code)
                if not ver_sel:
                    # 如果没找到验证码输入框，尝试一些常见替代方法
                    try:
                        page.fill('input[placeholder*="验证码"]', code)
                        ver_sel = 'input[placeholder*="验证码"]'
                    except Exception:
                        logger.error("无法找到验证码输入框，放弃此手机号（但验证码已返回）")
                        # 仍然尝试继续清空并请求新手机号
                        try:
                            if sel_used:
                                page.fill(sel_used, "")
                        except Exception:
                            pass
                        continue

                # 点击登录
                clicked_login = _try_click(page, LOGIN_BUTTON_SELECTORS)
                if not clicked_login:
                    logger.warning("未能点击登录按钮，尝试通过常见选择器点击或回退重试。")
                    try:
                        page.click("button:has-text('登录')", timeout=2000)
                        clicked_login = "button:has-text('登录')"
                    except Exception:
                        logger.error("无法触发登录按钮，放弃本次登录尝试（会清空手机号并重试新手机号）")
                        try:
                            if sel_used:
                                page.fill(sel_used, "")
                        except Exception:
                            pass
                        continue

                # 同意隐私弹窗（若存在）
                try:
                    _try_click(page, ["button:has-text('同意并登录')"])
                except Exception:
                    pass

                # 等待登录完成（可根据页面情况更改检测逻辑）
                time.sleep(4)
                # 简单判断是否登录成功（查找用户中心等元素）
                success = False
                success_text_candidates = ["尊敬的会员", "全部订单", "我的钱包", "我的工具", "退出登录"]
                for txt in success_text_candidates:
                    if page.locator(f"text={txt}").count() > 0:
                        success = True
                        break

                # 获取 cookies 并保存
                cookies = context.cookies()
                cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                save_cookie_to_redis(cookies, phone)

                if success:
                    logger.success(f"登录并保存 cookie 成功。手机号={phone}")
                else:
                    logger.warning("登录可能未完全成功，但仍已保存当前上下文 Cookie（建议人工确认）")

                # 关闭浏览器实例并返回成功
                try:
                    browser.close()
                except Exception:
                    pass
                return True

            # 若循环被中断/达到上限等，关闭浏览器并返回 False（主循环将继续重试新浏览器）
            try:
                browser.close()
            except Exception:
                pass
            return False

    except Exception as e:
        logger.error(f"generate_one_cookie 异常: {e}")
        return False





def main_loop():
    phone_platform = PhonePlatform()
    phone_platform.login()

    while True:
        current_count = get_cookie_count()
        logger.info(f"当前 Cookie 数量: {current_count}/{COOKIE_POOL_SIZE}")

        if current_count >= COOKIE_POOL_SIZE:
            logger.info("🎉 Cookie 池已满，休眠 1 分钟...")
            time.sleep(60)
            continue

        # 每次生成一个 cookie（会在单个浏览器内循环换号直到拿到验证码并登录）
        ok = generate_one_cookie(phone_platform, headless=False, max_phone_attempts=None)
        if not ok:
            logger.warning("本次浏览器实例未能成功生成 cookie，将短暂等待后用新浏览器重试。")
            time.sleep(3)
            continue

        # 稍作停顿，避免过快打开大量浏览器
        time.sleep(2)

if __name__ == "__main__":
    main_loop()
