import time
import requests
import loguru


class PhonePlatform:
    def __init__(self):
        self.host = "54.178.12.32:8000"
        self.username = "stxc"
        self.password = "f613"
        self.product_id = "236"
        self.token = None
        self.phone_number = None

    def login(self):
        """
        登录接口
        返回示例:
        {
            "code":200, "message":"成功",
            "result":{"token":"xxxxx"}
        }
        """
        api = f"http://{self.host}/api/user/apiLogin"
        method = "get"
        params = {
            "username": self.username,
            "password": self.password,
        }
        resp = self.request(api, params, method)
        try:
            if self.is_success(resp):
                self.token = resp.json()["result"]["token"]
                loguru.logger.info("✅ 登录成功")
            else:
                raise RuntimeError(f"登录失败: {resp.text}")
        except Exception as e:
            loguru.logger.error(f"❌ 登录异常: {e}")
        return self.token

    def get_phone_number(self):
        """
        获取手机号
        {
            "code":200,"message":"成功","result":{"phones":"13609021890"}
        }
        """
        api = f"http://{self.host}/api/phone/getPhone"
        method = "get"
        phone_number = None
        params = {
            "productId": self.product_id,
            "username": self.username,
            "token": self.token,
        }
        resp = self.request(api, params, method)
        try:
            if self.is_success(resp):
                phone_number = resp.json()["result"]["phones"]
                self.phone_number = phone_number
                loguru.logger.info(f"📞 获取号码成功: {phone_number}")
            else:
                raise RuntimeError(f"获取号码失败: {resp.text}")
        except Exception as e:
            loguru.logger.error(f"❌ 获取号码异常: {e}")
        return phone_number

    def get_verify_code(self):
        """
        轮询获取验证码（最多等待60秒）
        每3秒请求一次
        """
        api = f"http://{self.host}/api/phone/getCode"
        method = "get"
        params = {
            "productId": self.product_id,
            "username": self.username,
            "phone": self.phone_number,
            "token": self.token,
        }

        verify_code = None
        status = 2  # 默认无验证码
        start_time = time.time()
        timeout = 60
        interval = 3

        while True:
            try:
                resp = self.request(api, params, method)
                if self.is_success(resp):
                    result = resp.json().get("result", {})
                    if result.get("status") == 1:
                        verify_code = result.get("code")
                        status = 1
                        loguru.logger.info(f"✅ 获取验证码成功: {verify_code}")
                        break
                    else:
                        loguru.logger.info("⏳ 验证码暂未生成，继续等待...")
                else:
                    loguru.logger.warning(f"接口返回非成功状态: {resp.text}")
            except Exception as e:
                loguru.logger.error(f"获取验证码出错: {e}")
                break

            if time.time() - start_time > timeout:
                loguru.logger.warning("⚠️ 获取验证码超时（超过60秒仍无结果）")
                break

            time.sleep(interval)

        # 反馈状态
        try:
            self.feedback_status(status)
        except Exception as e:
            loguru.logger.error(f"反馈状态时出错: {e}")

        return verify_code

    def feedback_status(self, result: int):
        """
        [status 参数值为数字型]
        1-成功
        2-无验证码
        3-已注册
        4-注册失败
        """
        api = f"http://{self.host}/api/phone/reportResult"  # 修复host未替换问题
        method = "get"
        params = {
            "productId": self.product_id,
            "username": self.username,
            "token": self.token,
            "result": result,
            "phone": self.phone_number,
        }
        resp = self.request(api, params, method)
        try:
            if self.is_success(resp):
                loguru.logger.info("📤 状态反馈成功")
            else:
                loguru.logger.info(resp.text)
                raise RuntimeError(f"反馈失败: {resp.text}")
        except Exception as e:
            loguru.logger.error(f"❌ 状态反馈异常: {e}")

    def request(self, url: str, params: dict, method: str = "get", data=None) -> requests.Response:
        """
        实际发起请求
        """
        resp = None
        if data is None:
            data = {}
        try:
            if method.lower() == "get":
                resp = requests.get(url, params=params, timeout=10)
            elif method.lower() == "post":
                resp = requests.post(url, params=params, data=data, timeout=10)
            else:
                raise ValueError(f"不支持的请求方法: {method}")
        except requests.RequestException as e:
            loguru.logger.error(f"请求异常: {e}")
        return resp

    def is_success(self, resp: requests.Response):
        try:
            return resp and resp.status_code == 200 and resp.json().get("code") == 200
        except Exception:
            return False

    def run(self):
        """
        登录 -> 获取号码 -> 获取验证码
        如果验证码未获取成功则重新换号继续
        """
        if not self.login():
            loguru.logger.error("❌ 登录失败，无法继续执行")
            return None

        verify_code = None
        attempt = 0

        while not verify_code:
            attempt += 1
            loguru.logger.info(f"===== 第 {attempt} 次尝试获取验证码 =====")

            phone_number = self.get_phone_number()
            if not phone_number:
                loguru.logger.warning("⚠️ 获取手机号失败，等待3秒后重试")
                time.sleep(3)
                continue

            verify_code = self.get_verify_code()
            if verify_code:
                loguru.logger.success(f"🎉 成功获取验证码: {verify_code}")
                break
            else:
                loguru.logger.warning("未能获取到验证码，将重新获取新手机号重试...")
                time.sleep(3)

        return verify_code



if __name__ == '__main__':
    phone_platform = PhonePlatform()
    phone_platform.login()
    phone_platform.get_phone_number()
    loguru.logger.info(phone_platform.feedback_status(2))