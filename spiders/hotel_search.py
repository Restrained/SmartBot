# ctrip_hotel_search.py
import sys
import time
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

def run(hotel_name: str, output_file: str = "getHotelList_response.json"):
    with sync_playwright() as p:
        # 启动有头浏览器，方便手动登录
        browser = p.chromium.launch(headless=False)
        # 可模拟移动视口（可选）
        context = browser.new_context(
            viewport={"width": 375, "height": 812},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 13_6 like Mac OS X) "
                       "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.2 Mobile/15E148 Safari/604.1"
        )
        page = context.new_page()

        try:
            print("打开 https://m.ctrip.com/html5/ ...")
            page.goto("https://m.ctrip.com/html5/", wait_until="domcontentloaded", timeout=60000)

            # 等待用户手动登录
            print("\n请在打开的浏览器窗口手动完成登录（如果已登录可直接回车继续）。")
            input("登录完成后在此终端按回车继续...")

            # 点击酒店频道
            print("点击酒店频道（#c_hotel）...")
            try:
                page.click("a#c_hotel", timeout=15000)
            except PWTimeoutError:
                # 备用点击：尝试通过文本匹配点击
                print("直接 #c_hotel 点击失败，尝试通过文本 '酒店' 点击...")
                page.locator("a:has-text('酒店')").click(timeout=15000)

            # 等待页面稳定
            print("等待页面加载稳定...")
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except PWTimeoutError:
                # 继续也行
                pass

            # 定位输入框并输入 hotel_name
            print(f"查找目的地输入框并输入：{hotel_name}")
            # 优先尝试常见的 placeholder / input 选择器
            input_selectors = [
                "input[placeholder*='位置/品牌/酒店']",
                "input[placeholder*='位置']",
                "input[placeholder*='品牌']",
                "input[placeholder*='酒店']",
                "input[type='search']",
                "input[type='text']"
            ]
            input_clicked = False
            for sel in input_selectors:
                try:
                    locator = page.locator(sel)
                    if locator.count() > 0:
                        locator.first.click(timeout=8000)
                        locator.first.fill(hotel_name, timeout=8000)
                        input_clicked = True
                        break
                except Exception:
                    continue

            if not input_clicked:
                # 有些页面用 span 做伪输入，尝试点击包含那段提示文字的元素，再发送键入
                try:
                    span_loc = page.locator("text=位置/品牌/酒店")
                    if span_loc.count() > 0:
                        span_loc.first.click()
                        # 尝试聚焦到第一个可编辑 input 或 textarea
                        page.keyboard.type(hotel_name)
                        input_clicked = True
                except Exception:
                    pass

            if not input_clicked:
                print("⚠️ 未能精确定位到输入框，尝试在 body 上直接键入（作为最后手段）...")
                page.keyboard.type(hotel_name)

            # 回车确认选择（按回车）
            print("发送回车以确认目的地选择...")
            page.keyboard.press("Enter")
            # 等待回到主界面 / 结果页稳定
            time.sleep(1.2)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except PWTimeoutError:
                pass

            # 点击查询按钮
            print("点击 查询 按钮...")
            # 尝试多个可能的选择器
            search_selectors = [
                "div.inquireBtn_searchBtn__8LJwj",                # 你给出的 class
                "div:has-text('查 询')",                           # 文本匹配（带空格）
                "div:has-text('查询')",                            # 文本匹配（无空格）
                "button:has-text('查询')",
                "button:has-text('查 询')",
            ]
            clicked_search = False
            for sel in search_selectors:
                try:
                    loc = page.locator(sel)
                    if loc.count() > 0:
                        loc.first.click(timeout=10000)
                        clicked_search = True
                        break
                except Exception:
                    continue

            if not clicked_search:
                # 作为最后手段，使用 XPath 定位可能的按钮
                try:
                    page.locator("//div[contains(@class,'inquireBtn') and contains(., '查')]").first.click(timeout=10000)
                    clicked_search = True
                except Exception:
                    pass

            if not clicked_search:
                print("⚠️ 未能点击查询按钮，请检查页面，并手动在浏览器点击查询按钮后回车继续。")
                input("手动点击查询后在此终端按回车继续...")

            # 等待并捕获 getHotelList 接口响应
            target_substr = "restapi/soa2/25850/getHotelList"
            print(f"等待接口响应包含：{target_substr} ...（最多等待 30 秒）")
            try:
                response = page.wait_for_response(lambda r: target_substr in r.url and r.status == 200, timeout=30000)
                print("接口响应收到，读取 JSON ...")
                try:
                    data = response.json()
                except Exception:
                    # 有时候 response.json() 会失败（非 JSON），改为读取文本
                    data_text = response.text()
                    try:
                        data = json.loads(data_text)
                    except Exception:
                        data = {"raw_text": data_text}

                # 保存到文件并打印简要信息
                out_path = Path(output_file)
                out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
                print(f"接口 JSON 已保存到: {out_path.resolve()}")
                print("---- 接口返回 JSON 摘要（前500字符） ----")
                s = json.dumps(data, ensure_ascii=False)
                print(s[:500] + ("..." if len(s) > 500 else ""))
                return data

            except PWTimeoutError:
                print("等待接口响应超时（30s）。尝试扫描最近的网络响应以寻找目标接口...")
                # 作为回退，遍历最近响应
                for resp in context.pages[-1].context._connection._last_response_cache if False else []:
                    pass
                print("回退方法没有找到响应。你可以在浏览器开发者工具/network 查看接口是否发出。")
                return None

        finally:
            # 不立刻关闭浏览器，保留给你调试（可按需注释）
            print("脚本完成（浏览器窗口保持打开，按任意键后关闭）。")
            try:
                input("按回车关闭浏览器并退出...")
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python ctrip_hotel_search.py \"酒店名称\"")
        sys.exit(1)
    name = sys.argv[1]
    run(name)
