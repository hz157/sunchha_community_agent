import requests
from utils.config import get_config_value

# 获取配置文件中的社区API地址
community_api = get_config_value('community_api')
# 获取配置文件中的用户代理
user_agent = get_config_value('user_agent')

def getManuf():
    url = f"{community_api.rstrip('/')}/manufacturer/all"
    resp = requests.get(url, timeout=30, headers={"User-Agent": user_agent})
    resp.raise_for_status()
    return resp.json()['data']

def getManufByName(name):
    url = f"{community_api.rstrip('/')}/manufacturer/name?query={name}"
    resp = requests.get(url, timeout=30, headers={"User-Agent": user_agent})
    resp.raise_for_status()
    return resp.json()['data']

def getCommand(manuf_id: str):
    url = f"{community_api.rstrip('/')}/command/manuf?query={manuf_id}"
    resp = requests.get(url, timeout=30, headers={"User-Agent": user_agent})
    resp.raise_for_status()
    return resp.json()['data']