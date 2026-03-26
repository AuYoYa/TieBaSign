# -*- coding:utf-8 -*-
import os
import requests
import hashlib
import time
import copy
import logging
import random

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ================= 日志 =================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ================= 常量 =================
LIKIE_URL = "http://c.tieba.baidu.com/c/f/forum/like"
TBS_URL = "http://tieba.baidu.com/dc/common/tbs"
SIGN_URL = "http://c.tieba.baidu.com/c/c/forum/sign"

TIMEOUT = 15  # ⭐ 拉长超时

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
}

SIGN_DATA = {
    '_client_type': '2',
    '_client_version': '9.7.8.0',
    '_phone_imei': '000000000000000',
    'model': 'MI+5',
    "net_type": "1",
}

SIGN_KEY = 'tiebaclient!!!'

# ================= Session增强 =================
def create_session():
    session = requests.Session()

    retry = Retry(
        total=3,
        backoff_factor=1,  # 指数退避：1s 2s 4s
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )

    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session

s = create_session()

# ================= 工具函数 =================
def safe_request(method, url, **kwargs):
    try:
        if method == "GET":
            return s.get(url, timeout=TIMEOUT, **kwargs)
        elif method == "POST":
            return s.post(url, timeout=TIMEOUT, **kwargs)
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {url} | {e}")
        return None


def encodeData(data):
    s_str = ''
    for k in sorted(data.keys()):
        s_str += k + '=' + str(data[k])
    sign = hashlib.md5((s_str + SIGN_KEY).encode('utf-8')).hexdigest().upper()
    data.update({"sign": sign})
    return data


# ================= 核心功能 =================
def get_tbs(bduss):
    logger.info("获取 tbs")

    headers = copy.copy(HEADERS)
    headers.update({"Cookie": f"BDUSS={bduss}"})

    for i in range(3):
        res = safe_request("GET", TBS_URL, headers=headers)
        if res:
            try:
                return res.json()["tbs"]
            except Exception as e:
                logger.error(f"解析 tbs 失败: {e}")

        time.sleep(2)

    logger.error("获取 tbs 失败")
    return None


def get_favorite(bduss):
    logger.info("获取关注贴吧")

    data = {
        'BDUSS': bduss,
        '_client_type': '2',
        '_client_version': '9.7.8.0',
        '_phone_imei': '000000000000000',
        'from': '1008621y',
        'page_no': '1',
        'page_size': '200',
        'model': 'MI+5',
        'net_type': '1',
        'timestamp': str(int(time.time())),
    }

    data = encodeData(data)

    res = safe_request("POST", LIKIE_URL, data=data)
    if not res:
        return []

    try:
        data = res.json()
    except:
        return []

    forums = []

    try:
        fl = data.get("forum_list", {})
        forums.extend(fl.get("non-gconforum", []))
        forums.extend(fl.get("gconforum", []))
    except:
        pass

    logger.info(f"获取到 {len(forums)} 个贴吧")
    return forums


def client_sign(bduss, tbs, fid, kw):
    logger.info(f"签到: {kw}")

    data = copy.copy(SIGN_DATA)
    data.update({
        "BDUSS": bduss,
        "fid": fid,
        "kw": kw,
        "tbs": tbs,
        "timestamp": str(int(time.time()))
    })

    data = encodeData(data)

    res = safe_request("POST", SIGN_URL, data=data)

    if not res:
        logger.error(f"签到失败（请求失败）: {kw}")
        return False

    try:
        r = res.json()
        if r.get("error_code") == "0":
            logger.info(f"签到成功: {kw}")
            return True
        else:
            logger.warning(f"签到失败: {kw} | {r}")
            return False
    except:
        logger.error(f"解析失败: {kw}")
        return False


# ================= 主逻辑 =================
def main():
    bduss_list = os.getenv("BDUSS")

    if not bduss_list:
        logger.error("未配置 BDUSS")
        return

    bduss_list = bduss_list.split('#')

    for idx, bduss in enumerate(bduss_list):
        logger.info(f"===== 开始账号 {idx+1} =====")

        tbs = get_tbs(bduss)
        if not tbs:
            continue

        forums = get_favorite(bduss)

        success = 0

        for f in forums:
            try:
                time.sleep(random.randint(1, 5))  # 防风控
                if client_sign(bduss, tbs, f["id"], f["name"]):
                    success += 1
            except Exception as e:
                logger.error(f"异常: {e}")

        logger.info(f"账号 {idx+1} 完成，成功 {success}/{len(forums)}")

    logger.info("全部完成")


if __name__ == "__main__":
    main()