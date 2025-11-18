import json
from dataclasses import dataclass
from typing import List, Optional, Any, Dict, Tuple


# ============================
# 数据模型
# ============================

@dataclass
class Discount:
    name: str
    amount: float
    desc: str


@dataclass
class Dialog:
    title: str
    date_range: str
    room_name: str
    room_code: str
    fee: float
    discount_total: float
    discounts: List[Discount]
    final_price: Optional[float] = None


@dataclass
class Room:
    id: str
    name: str
    code: str
    img: Optional[str]
    bed: Optional[str]
    size: Optional[str]
    people: Optional[str]
    breakfast: Optional[str]
    cancel: Optional[str]
    old_price: Optional[float]
    price: Optional[float]
    discounts: List[str]
    discount_desc: Optional[str]
    residue: Optional[str]


# ============================
# 安全辅助函数
# ============================

def safe_get(d: dict, key: str, default=None):
    """安全取值，防止KeyError"""
    if not isinstance(d, dict):
        return default
    return d.get(key, default)


def safe_float(value: Any) -> Optional[float]:
    """尝试把值转为float"""
    try:
        return abs(int(str(value).replace("¥", "").replace("-¥", "").strip()))
    except Exception:
        return None


# ============================
# 主解析逻辑
# ============================

def parse_room(file_path:str =None, json_content: Dict = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    解析酒店 JSON 文件并返回房间信息和费用明细对话框信息
    """
    room_info = []
    dialogs = []

    try:
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                json_content = json.load(f)

        data = json_content.get("data", {})

        # 1️⃣ 解析 physicRoomMap (房型基础信息)
        physic_room_list = []
        for room_id, v in data.get("physicRoomMap", {}).items():
            name = safe_get(v, "name")
            physic_id = safe_get(v, "id")
            bed_info = safe_get(v.get("bedInfo", {}), "title")
            area_info = safe_get(v.get("areaInfo", {}), "title")
            bed_count = safe_get(v.get("houseTypeInfo", {}), "bedCount", 1)
            people_info = f"{max(2, bed_count)}人入住"
            picture_url = None

            # 图片列表安全取值
            pic_list = safe_get(v, "pictureInfo", [])
            if isinstance(pic_list, list) and pic_list:
                picture_url = safe_get(pic_list[0], "url")

            physic_room_list.append({
                "room_physic_id": physic_id,
                "room_name": name,
                "picture_url": picture_url,
                "bed_info": bed_info,
                "area_info": area_info,
                "people_info": people_info,
            })

        # 2️⃣ 解析 saleRoomMap (售卖房间信息)
        for physic_item in physic_room_list:
            room_physic_id = physic_item["room_physic_id"]

            for _, v in data.get("saleRoomMap", {}).items():
                if safe_get(v, "physicalRoomId") != room_physic_id:
                    continue

                room_id = safe_get(v, "id")
                room_code = safe_get(v, "roomCode")
                meal_title = safe_get(v.get("mealInfo", {}), "title")
                cancel_title = safe_get(v.get("cancelInfo", {}), "title")

                price_info = safe_get(v, "priceInfo", {})
                price = safe_float(safe_get(price_info, "price"))
                old_price = safe_get(price_info, "deletePricewithOutCurrency") or price


                discounts, discount_desc = [], ""
                for label in safe_get(v, "priceLabelList", []):
                    if label.get("type") == "discountTag":
                        discount_desc = label.get("text", "")
                    else:
                        discounts.append(label.get("text", ""))

                residue = ""
                inspire_info = safe_get(v, "inspireInfo", [])
                if inspire_info and isinstance(inspire_info, list):
                    residue = safe_get(inspire_info[0], "title", "")

                if price:  # 仅保留有价格的房型
                    room_info.append({
                        "group_id": room_physic_id,
                        "id": room_id,
                        "name": physic_item["room_name"],
                        "code": room_code,
                        "img": physic_item["picture_url"],
                        "bed": physic_item["bed_info"],
                        "size": physic_item["area_info"],
                        "people": physic_item["people_info"],
                        "breakfast": meal_title,
                        "cancel": cancel_title,
                        "old_price": old_price,
                        "price": price,
                        "discounts": discounts,
                        "discount_desc": discount_desc,
                        "residue": residue,
                    })

                # 3️⃣ 解析费用对话框信息
                total_price_info = safe_get(v, "totalPriceInfo")
                if total_price_info:
                    dialog_info = parse_dialog(
                        date_range="未知日期",
                        room_name=physic_item["room_name"],
                        room_code=room_code,
                        promotion_dict=total_price_info,
                        old_price= old_price
                    )
                    dialogs.append(dialog_info)

        return room_info, dialogs

    except FileNotFoundError:
        print(f"❌ 文件未找到: {file_path}")
    except json.JSONDecodeError:
        print(f"❌ JSON 格式错误: {file_path}")
    except Exception as e:
        print(f"❌ 未知错误: {e}")

    return [], []


# ============================
# 费用详情解析
# ============================

def parse_dialog(date_range: str, room_name: str, room_code: str, promotion_dict: Dict, old_price:str) -> Dict:
    """解析促销价格明细"""
    try:
        quantity_days = safe_get(promotion_dict, "quantityDays", {})
        fee = safe_float(safe_get(quantity_days, "content")) or old_price

        discount_total = safe_float(safe_get(promotion_dict, "totalDiscount")) or 0
        discounts = []
        for item in safe_get(promotion_dict, "promotionItems", []):
            title = safe_get(item, "title", "")
            amount = safe_float(safe_get(item, "amount"))
            discounts.append({
                "name": title,
                "amount": amount,
                "desc": title,
            })

        return {
            "title": "费用明细",
            "date_range": date_range,
            "room_name": room_name,
            "room_code": room_code,
            "fee": fee,
            "discount_total": discount_total,
            "discounts": discounts,
        }

    except Exception as e:
        print(f"⚠️ 解析费用信息时出错 ({room_name}): {e}")
        return {}


# ============================
# 示例
# ============================

if __name__ == "__main__":
    hotel, dialogs = parse_room(r"C:\Users\95826\Documents\携程项目\json\hotel_detail.json")

    print(f"✅ 成功解析 {len(hotel)} 个房型，{len(dialogs)} 条费用详情")
    print(json.dumps(hotel[:1], ensure_ascii=False, indent=2))
    print(json.dumps(dialogs[:1], ensure_ascii=False, indent=2))
