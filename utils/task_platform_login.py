# pip install pycryptodome
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
import base64


PUBLIC_KEY = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCFkbFivayA0NDNBYMfXr5ZpnPj5c8Ead10yLCmGz7yyE0/1EGDTRF80YxwzhShWUBtRI9ttwn6+zaiCOjznKSgd5E/dIGXRQ+adMtFUZQxgveXrl7x/C/2idkkPLu/oWeq7+PT7ajbQLjbeZvg3tJzJhOVXPiD6RAouSVbdp4JowIDAQAB"

def make_pem_from_base64(b64_body: str) -> str:
    # 把长串按 64 字符换行，包上 PEM 头尾
    lines = [b64_body[i:i+64] for i in range(0, len(b64_body), 64)]
    body = "\n".join(lines)
    pem = "-----BEGIN PUBLIC KEY-----\n" + body + "\n-----END PUBLIC KEY-----"
    return pem

def rsa_encrypt_base64(plaintext: str, pubkey_b64_body: str = PUBLIC_KEY) -> str:
    # pubkey_b64_body: JS 文件里的 "MIGfMA0G..." 这种纯 base64 body（没有 -----BEGIN-----）
    pem = make_pem_from_base64(pubkey_b64_body)
    key = RSA.import_key(pem)
    cipher = PKCS1_v1_5.new(key)
    ciphertext_bytes = cipher.encrypt(plaintext.encode('utf-8'))
    return base64.b64encode(ciphertext_bytes).decode()

# 示例（把下面 nn 替换成 JS 文件里实际的字符串）

if __name__ == '__main__':
    plaintext = "sx001_759528"   # phone + "_" + code（与 JS 拼法一致）
    cipher_b64 = rsa_encrypt_base64(plaintext)
    print(cipher_b64)
