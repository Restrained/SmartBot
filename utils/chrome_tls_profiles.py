#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/5/8 15:56
# @Author  : AllenWan
# @File    : chrome_tls_profiles.py
# @Desc    ：
import random
from requests_go.tls_config import TLSConfig

CHROME_PROFILES = [
    # {
    #     "ja3": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-21,29-23-24,0",
    #     "sig_algs": [
    #         "ecdsa_secp256r1_sha256",
    #         "rsa_pkcs1_sha256",
    #         "rsa_pss_rsae_sha256",
    #         "rsa_pkcs1_sha384",
    #         "ecdsa_secp384r1_sha384",
    #         "rsa_pss_rsae_sha384"
    #     ],
    #     "alpn": ["h2", "http/1.1"],
    #
    # },
    # {
    #     "ja3": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-21,29-23-24-25,0",
    #     "sig_algs": [
    #         "ecdsa_secp256r1_sha256",
    #         "rsa_pkcs1_sha256",
    #         "rsa_pss_rsae_sha256",
    #         "rsa_pkcs1_sha384",
    #         "ecdsa_secp384r1_sha384",
    #         "rsa_pss_rsae_sha384",
    #         "rsa_pkcs1_sha512",
    #         "rsa_pss_rsae_sha512"
    #     ],
    #     "alpn": ["h2", "http/1.1"],
    #
    # },
    # {
    #     "ja3": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-21,29-23-24,0",
    #     "sig_algs": [
    #         "ecdsa_secp256r1_sha256",
    #         "rsa_pkcs1_sha256",
    #         "rsa_pss_rsae_sha256",
    #         "rsa_pkcs1_sha384",
    #         "ecdsa_secp384r1_sha384",
    #         "rsa_pss_rsae_sha384",
    #         "rsa_pkcs1_sha512",
    #         "rsa_pss_rsae_sha512"
    #     ],
    #     "alpn": ["h2", "http/1.1"],
    # },
    {
        "ja3": "771,49195-49196-52393-49200-49199-49172-49171-52392-49162-49161-49192-49191-49188-49187-49160-49170-156-157-53-47,0-10-11-13-35-23-65281,29-23-24,0",
        "sig_algs": [
            "rsa_pkcs1_sha256",
            "ecdsa_secp256r1_sha256",
            "rsa_pkcs1_sha384",
            "rsa_pkcs1_sha1"
        ],
        "alpn": ["http/1.1"],
    }

]


def get_random_chrome_tls_config():
    profile = random.choice(CHROME_PROFILES)

    tls = TLSConfig()
    tls.ja3 = profile["ja3"]
    tls.pseudo_header_order = [":method", ":authority", ":scheme", ":path"]
    tls.tls_extensions.cert_compression_algo = ["brotli"]
    tls.tls_extensions.supported_signature_algorithms = profile["sig_algs"]
    tls.tls_extensions.supported_versions = ["GREASE", "1.3", "1.2"]
    tls.tls_extensions.psk_key_exchange_modes = ["PskModeDHE"]
    tls.tls_extensions.key_share_curves = ["GREASE", "X25519"]
    tls.http2_settings.settings = {
        "HEADER_TABLE_SIZE": 65536,
        "ENABLE_PUSH": 0,
        "MAX_CONCURRENT_STREAMS": 1000,
        "INITIAL_WINDOW_SIZE": 6291456,
        "MAX_HEADER_LIST_SIZE": 262144
    }
    tls.http2_settings.settings_order = [
        "HEADER_TABLE_SIZE",
        "ENABLE_PUSH",
        "MAX_CONCURRENT_STREAMS",
        "INITIAL_WINDOW_SIZE",
        "MAX_HEADER_LIST_SIZE"
    ]
    tls.http2_settings.connection_flow = 15663105

    return tls
