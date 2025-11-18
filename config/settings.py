import os

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