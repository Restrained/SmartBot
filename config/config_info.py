#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/11/27 15:23
# @Author  : AllenWan
# @File    : config_info.py
import base64


class MongoConfig:
    host = '192.168.0.41'
    port = 37017
    username = "c3BpZGVy"
    password = "SlFkeEt0UlJ2czRRanFhejE=d"
    database = 'spider'
    auth_database = 'spider'


class RedisConfig:
    host = '192.168.0.41'
    port = 16379
    password = "SHp4YzIwMjM="
    database = 8



SPECIAL_JOURNAL_LIST = [
    "中国微生态学杂志",
    "环境化学",
    "生态毒理学报",
    "岩石学报",
    "光电工程",
    "第四纪研究",
    "临床耳鼻咽喉头颈外科杂志"
]

if __name__ == '__main__':
    print(base64.b64decode(MongoConfig.password).decode("utf-8"),)