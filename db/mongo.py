#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/11/27 10:05
# @Author  : AllenWan
# @File    : mongo.py
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/8/22 16:40
# @Author  : AllenWan
# @File    : mongo.py
# @Desc    ：
from loguru import logger
from pymongo import MongoClient, UpdateOne, InsertOne, ASCENDING, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database
from typing import Optional, Dict, Any, List, Iterable, Tuple
import threading

from config import settings





class MongoClientSingleton:
    """
        MongoDB 客户端单例封装类

        功能说明：
        -----------
        1. **单例模式**
           - 通过线程锁 (`threading.Lock`) 保证在多线程环境下只会创建一个 `MongoClient` 实例，
             避免重复连接 MongoDB。

        2. **基础连接**
           - 自动从 `config.settings` 读取 MongoDB URI 和数据库名称。
           - 提供 `client` 和 `db` 属性，分别暴露底层 `MongoClient` 和默认 `Database`。

        3. **常用操作**
           - `find()`       : 查询文档，支持 limit。
           - `find_one()`       : 单条查询。
           - `update()`     : 批量更新文档，支持 upsert。
            - `find_one_and_update()`       : 单条查询并更新，且能返回查询结果。
           - `insert_one()` : 插入单条文档。
           - `insert_many()`: 批量插入文档。
           - `delete_many()`: 批量删除文档。

        4. **增强功能**
           - `create_ttl_index()`      : 支持创建ttl索引功能。
           - `write()`      : 封装批量写操作，支持 Insert / Update 混合，底层基于 `bulk_write`。
           - `iter_data()`  : 批量迭代读取数据，按块返回（游标遍历）。
           - `batch_data()` : 使用聚合管道方式批量读取，支持 skip / group / sort / project 等复杂场景。

        使用示例：
        -----------
        # >>> mongo = MongoClientSingleton()
        # >>> mongo.insert_one("users", {"name": "Alice", "age": 20})
        # >>> docs = mongo.find("users", {"age": {"$gte": 18}}, limit=5)
        # >>> mongo.update("users", {"active": True}, {"age": {"$gte": 18}})
        # >>> for batch in mongo.iter_data("users", count=1000):
        # ...     print(batch)

        适用场景：
        -----------
        - 项目中需要全局复用 MongoDB 连接，避免频繁创建和销毁连接。
        - 封装常用的 CRUD 及批量操作，提升代码复用性和可维护性。
        - 需要支持大规模数据迭代、批量导入导出等场景。
        """
    _instances: Dict[str, "MongoClientSingleton"] = {}  # 按 db_name 存储单例
    _lock = threading.Lock()

    def __new__(cls, uri: str = None, db_name: str = None):
        """
        按 db_name 创建或获取单例实例
        """
        db_name = db_name or settings.MONGO_DB  # 默认数据库名
        with cls._lock:
            if db_name not in cls._instances:
                cls._instances[db_name] = super().__new__(cls)
            return cls._instances[db_name]

    def __init__(self, uri: str = None, db_name: str = None):
        if getattr(self, "_initialized", False):
            return

        self._uri = uri or settings.MONGO_URI
        self._db_name = db_name or settings.MONGO_DB
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None

        self.connect()
        self._initialized = True

    @property
    def client(self) -> MongoClient:
        """对外暴露 MongoClient"""
        return self._client

    @property
    def db(self) -> Database:
        """ 对外暴露 Database"""
        return self._db

    def connect(self):
        if self._client is None:
            self._client = MongoClient(self._uri, tz_aware=True)
            self._db = self._client[self._db_name]
            logger.info(f"Connected to MongoDB {self._uri}, db={self._db_name}")


    # ================= 通用方法 =================
    def find(self,
             collection: str,
             query: Dict[str, Any] = None,
             limit: int =0,
             database: str = None,
             sort: Optional[List[Tuple[str, int]]] = None,
             projection: Optional[Dict[str, Any]] = None
             ) -> List[Dict[str, Any]]:
            """
            通用查询方法，支持 limit + sort + projection

            Args:
                collection: 集合名
                query: 查询条件，例如 {"status": "online"}
                limit: 限制返回数量，0表示不限制
                database: 数据库名，默认为当前数据库
                sort: 排序条件，例如 [("mem_usage", 1), ("cpu_usage", -1)]
                projection: 投影条件，控制返回字段，例如 {"_id": 0, "name": 1, "status": 1}
                           1表示包含，0表示排除

            Returns:
                查询结果列表
           """
            database = database or self._db_name
            col: Collection = self._client[database][collection]
            query = query or {}
            cursor = col.find(query, projection=projection)

            if sort:
                cursor = cursor.sort(sort)
            if limit > 0:
                cursor = cursor.limit(limit)
            return list(cursor)

    def find_one(self, collection: str, query: Dict[str, Any] = None, database: str = None) -> Dict[str, Any]:
        database = database or self._db_name
        col: Collection = self._client[database][collection]
        query = query or {}
        return col.find_one(query)

    def update(self, collection: str, update_data: Dict[str, Any], query: Dict[str, Any] = None, database: str = None, upsert: bool = True, use_set: bool = True):
        """
        支持 $set / $inc 等 MongoDB 操作符。

        :param collection: 集合名称
        :param update_data: 更新数据，可以是 {'field': value}，也可以是 {'$inc': {'counter': 1}}
        :param query: 查询条件
        :param database: 数据库名
        :param upsert: 是否 upsert
        :param use_set: 是否默认用 $set 包裹 update_data
        """
        database = database or self._db_name
        col: Collection = self._client[database][collection]
        query = query or {}

        if any(k.startswith("$") for k in update_data.keys()):
            update_doc = update_data
        else:
            update_doc = {"$set": update_data} if use_set else update_data
        return col.update_many(query, update_doc, upsert=upsert)

    def find_one_and_update(
            self,
            collection: str,
            query: Dict[str, Any],
            update_data: Dict[str, Any],
            database: str = None,
            upsert: bool = False,
            use_set: bool = True,
            projection: Optional[Dict[str, Any]] = None,
            sort: Optional[List[tuple]] = None,
            return_new: bool = True,
    ) -> Dict[str, Any]:
        """
          查找并更新一个文档，返回更新后的结果。

          :param collection: 集合名称
          :param query: 查询条件
          :param update_data: 更新数据，可以是 {'field': value}，也可以是 {'$inc': {'counter': 1}}
          :param database: 数据库名
          :param upsert: 是否 upsert
          :param use_set: 是否默认用 $set 包裹 update_data
          :param projection: 返回字段，如 {"field": 1, "_id": 0}
          :param sort: 排序条件，如 [("created_at", 1)]
          :param return_new: 是否返回更新后的文档（默认 True）
        """
        database = database or self._db_name
        col: Collection = self._client[database][collection]

        # 判断 update_data 是原子操作符还是普通字典
        if any(k.startswith("$") for k in update_data.keys()):
            update_doc = update_data
        else:
            update_doc = {"$set": update_data} if use_set else update_data

        return col.find_one_and_update(
            query,
            update_doc,
            projection=projection,
            sort=sort,
            upsert=upsert,
            return_document=ReturnDocument.AFTER if return_new else ReturnDocument.BEFORE,
        )

    def insert_one(self, collection: str, document: Dict[str, Any], database: str = None):
        database = database or self._db_name
        col: Collection = self._client[database][collection]
        return col.insert_one(document)

    def insert_many(self, collection: str, documents: List[Dict[str, Any]], database: str = None,  ordered: bool = True):
        database = database or self._db_name
        col: Collection = self._client[database][collection]
        return col.insert_many(documents, ordered=ordered)

    def delete_many(self, collection: str, query: Dict[str, Any] = None, database: str = None):
        database = database or self._db_name
        col: Collection = self._client[database][collection]
        query = query or {}
        return col.delete_many(query)

    def create_ttl_index(self, collection: str, field: str = "time", expire_seconds: int = 7 * 24 * 3600,
                         database: Optional[str] = None):
        """
        在指定集合上创建 TTL 索引
        :param collection: 集合名
        :param field: 索引字段名
        :param expire_seconds: 过期时间（秒）
        :param database: 数据库名，可选
        """
        database = database or self._db_name
        col: Collection = self._client[database][collection]
        try:
            col.create_index(
                [(field, ASCENDING)],
                expireAfterSeconds=expire_seconds
            )
            # logger.info(f"TTL index created on {database}.{collection}({field}), expireAfterSeconds={expire_seconds}")
        except Exception as e:
            logger.warning(f"Failed to create TTL index on {database}.{collection}: {e}")

    # ======================= 重写方法 ===========================
    def write(
            self,
            collection: str,
            *items: Dict[str, Any],
            query: Optional[List[str]] = None,
            database: Optional[str] = None,
            **kwargs,
    ):
        """
        批量更新或者插入

        :param collection: 表名
        :param items: 需要写入的字段
        :param query: 过滤条件
        :param database: 数据库
        :param kwargs:
        :return:

            m = Mongo()
            # 插入模式
            m.write(
                'my_collection',
                *[{'name': 'kem', 'id': i} for i in range(10)]
            )

            # 更新模式
            m.write(
                'my_collection',
                *[{'name': 'kem', 'id': i} for i in range(10)],
                query=["id"]
            )

        """

        query = query or []
        action = kwargs.pop("action", "$set")  # default update operator
        upsert = kwargs.pop("upsert", True)  # default upsert mode
        update_op = kwargs.pop("update_op", None) or UpdateOne
        insert_op = kwargs.pop("insert_op", None) or InsertOne
        database = database or self._db_name
        col: Collection = self._client[database][collection]
        requests = []

        for index, item in enumerate(items):
            item = dict(item)
            if query:
                _query = {i: item.get(i) for i in query}
                requests.append(
                    update_op(filter=_query, update={action: item}, upsert=upsert)
                )
            else:
                requests.append(insert_op(dict(item)))

        return requests and col.bulk_write(
            requests, ordered=False
        )

    # ======================= 批量迭代器 ============================

    def iter_data(
            self,
            collection: str,
            query: Dict[str, Any] = None,
            projection: Dict[str, Any] = None,
            database: str = None,
            sort: Optional[List[tuple]] = None,
            skip: int = 0,
            count: int = 1000,
    ) -> Iterable[List[dict]]:
        """
        从 collection_name 获取迭代数据

        :param projection: 过滤字段
        :param collection: 表名
        :param query: 过滤条件
        :param sort: 排序条件
        :param database: 数据库
        :param skip: 要跳过多少
        :param count: 一次能得到多少
        :return:
        """
        database = database or self._db_name
        col: Collection = self._client[database][collection]
        sort = [sort] if (not isinstance(sort, list) and sort) else sort
        query = query or {}

        while True:
            data = list(
                col.find(
                    filter=query,
                    projection=projection,
                    skip=skip,
                    sort=sort,
                    limit=count,
                    allow_disk_use=True,
                )
            )
            if not data:
                return

            else:
                yield data
                skip += len(data)




    def batch_data(self,
                   collection: str,
                   query: Optional[dict] = None,
                   projection: Optional[dict] = None,
                   database: str = None,
                   group: Optional[dict] = None,
                   sort: Optional[list[tuple]] = None,
                   skip: int = 0,
                   count: int = 1000
                   ) -> Iterable[List[dict]]:
        """

         按批次迭代查询 MongoDB 集合中的数据，支持过滤、分组、投影、排序和跳过指定数量的数据。

        该方法基于 `_id` 进行批量分页（游标方式），每次返回 `count` 条数据，
        使用 `yield` 生成器逐批返回，适用于大数据量分批处理的场景。

        Args:
            collection (str): 集合名称。
            query (Optional[dict], 默认=None): 查询条件，相当于 MongoDB 的 `$match`。
            projection (Optional[dict], 默认=None): 返回字段选择，相当于 `$project`。
            database (str, 默认=None): 数据库名称，若未指定则使用默认库。
            group (Optional[dict], 默认=None): 分组条件，相当于 `$group` 聚合。
            sort (Optional[list[tuple]], 默认=None): 排序条件，例如 `[("age", 1), ("score", -1)]`。
            skip (int, 默认=0): 跳过的文档数量。
            count (int, 默认=1000): 每批次返回的最大文档数。

        Yields:
            List[dict]: 每次返回一批文档列表。

        Example:
            # >>> mongo = MongoClientSingleton()
            # >>> for batch in mongo.batch_data(
            # ...     "users",
            # ...     query={"age": {"$gte": 18}},
            # ...     projection={"_id": 0, "name": 1, "age": 1},
            # ...     sort=[("age", 1)],
            # ...     count=500
            # ... ):
            # ...     process(batch)
        """
        database = database if database else self._db_name
        col: Collection = self._client[database][collection]

        # 确定排序规则
        sort_condition = {"_id": 1}
        if sort:
            sort_condition.update({k: v for k, v in sort})

        # 获取创建要跳过数据量前一条的_id
        last_id = None
        if skip:
            skip_result = col.find_one(
                filter=query,
                skip=skip - 1,
                sort=list(sort_condition.items()))
            if not skip_result:
                return
            last_id = skip_result["_id"]

        while True:
            # 利用聚合操作查询，利用生成器逐段返回
            _pipeline: list[dict] = []
            query and _pipeline.append({"$match": query})
            group and _pipeline.append({"$group": group})
            sort_condition and _pipeline.append({"$sort": sort_condition})
            projection and _pipeline.append({"$project": projection})
            last_id and _pipeline.append({"$match": {"_id": {"$gt": last_id}}})
            _pipeline.append({"$limit": count})

            data: List[dict] = list(col.aggregate(_pipeline, allowDiskUse=True))

            if not data:
                return

            last_id = data[-1]["_id"]
            yield data

    def aggregate(self,
                  collection: str,
                  pipeline: List[Dict[str, Any]],
                  database: str = None,
                  allow_disk_use: bool = True,
                  batch_size: Optional[int] = 1000,
                ) -> Iterable[Dict[str, Any]]:
        """
        通用聚合查询方法，支持传入 pipeline。

        Args:
            collection (str): 集合名称
            pipeline (List[Dict[str, Any]]): 聚合管道
            database (Optional[str]): 数据库名，默认使用配置库
            allow_disk_use (bool): 是否允许使用磁盘缓冲，适合大数据量
            batch_size (int): 游标批量大小，默认 1000

        Yields:
            Dict[str, Any]: 每条文档结果
        """
        database = database if database else self._db_name
        col: Collection = self._client[database][collection]

        cursor = col.aggregate(pipeline,
                               allowDiskUse=allow_disk_use,
                               )

        if batch_size:
            cursor = cursor.batch_size(batch_size)

        for doc in cursor:
            yield doc

    def update_row(self, collection: str, database: str = None, query: Optional[dict] = None,
                   update: Optional[dict] = None, upsert=True):
        """
        删除指定collection
        :param upsert:
        :param update:
        :param query:
        :param collection:
        :param database:
        :return:
        """
        database = database if database else self._db_name

        self._client[database][collection].update_one(query, update, upsert=upsert)

if __name__ == "__main__":
    mongo_instance = MongoClientSingleton(settings.MONGO_URI, db_name="crawler")

    # print(mongo_instance.find("crawl_tasks", {"status": "pending"}, limit=500))
    # mongo_instance.update(
    #     "crawl_tasks",
    #     {
    #         "last_heartbeat": now_local(),
    #         "update_at": now_local(),
    #     },
    #     {"id": "a13f9c0f7c0d2f5bbf24c6f2"}
    # )