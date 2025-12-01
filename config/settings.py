import os
import base64

# =========================
# Mongo 配置
# =========================
MONGO_HOST = os.getenv('MONGO_HOST', '192.168.1.191')
MONGO_PORT = os.getenv('MONGO_PORT', 27017)
MONGO_USER = os.getenv('MONGO_USER', None)
MONGO_PASSWORD = os.getenv('MONGO_PASSWORD', None)
MONGO_DB = os.getenv('MONGO_DBNAME', 'admin')

# 统一拼接 Mongo URI
if MONGO_USER and MONGO_PASSWORD:
    MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}"
else:
    MONGO_URI = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}"


# =========================
# Redis 配置
# =========================
REDIS_HOST = "192.168.1.191"
REDIS_PORT = 6379
REDIS_DB = 0



# 任务平台账号列表
TASK_ACCOUNTS = [
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
    {"username": "sx011", "password": "713945"},
    {"username": "sx012", "password": "968059"},
    {"username": "sx013", "password": "614653"},
    {"username": "sx014", "password": "661445"},
    {"username": "sx015", "password": "709167"},
    {"username": "sx016", "password": "440226"},
    {"username": "sx017", "password": "877543"},
    {"username": "sx018", "password": "408832"},
    {"username": "sx019", "password": "814576"},
    {"username": "sx020", "password": "037306"},
    # 可以添加更多账号...
]


