from datetime import datetime, timedelta

def parse_checkin_checkout(check_in: str, check_out: str) -> dict:
    """日期格式转换 + 今日/明日判断"""
    def format_date(date_str: str):
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{d.month}月{d.day}日"

    def get_day_label(date_str: str):
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        if d == today:
            return "今天"
        elif d == today + timedelta(days=1):
            return "明天"
        else:
            week_map = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]
            return week_map[d.weekday()]

    return {
        "checkin_date": format_date(check_in),
        "checkin_day": get_day_label(check_in),
        "checkout_date": format_date(check_out),
        "checkout_day": get_day_label(check_out)
    }

# ✅ 示例测试
if __name__ == "__main__":

    result = parse_checkin_checkout("2025-11-15", "2025-11-16")
    print(result)
