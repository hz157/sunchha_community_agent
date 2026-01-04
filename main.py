import os
import platform
import subprocess
from utils.config import *
from cloud import api_client
from engine.inspector import query_manuf_command
from utils.target import read_target_info
from cloud.api_client import *
# from update.update import Updater
from utils.color import *

VERSION = "v1.0.0"
RELEASEDATE = "2025-12-28"
PLATFORM = None
RUN_MODE = get_config_value("run_mode").upper() 
    
def clear_console():
    """ 清空控制台 """
    global PLATFORM
    system_name = platform.system()
    if system_name == "Windows":
        os.system("cls")
        PLATFORM = "Windows"
    elif system_name in ["Linux", "Darwin"]:
        os.system("clear")
        PLATFORM = "Linux"

def welcome():
    """ 显示欢迎信息 """
    clear_console()
    # 免责声明
    print(COLOR_RED + """
⚠️ 免责声明：
本自动化程序仅建议用于进行巡检操作，并不建议使用此自动化程序进入使能模式执行配置命令等高危操作。
如使用该程序执行自动化配置命令造成的网络中断后果，请自行负责！
""" + COLOR_RESET)
    
    print(
        COLOR_CYAN +
        f"""
        ____                       _      _            
        / ___|  _   _  _ __    ___ | |__  | |__    __ _ 
        \___ \\ | | | || '_ \\  / __|| '_ \\ | '_ \\  / _` |
        ___) || |_| || | | || (__ | | | || | | || (_| |
        |____/  \\__,_||_| |_| \\___||_| |_||_| |_| \\__,_|

            Personal Homepage: https://www.bytesycn.com
            Github Repo: https://github.com/hz157/Sunchha  
            Version: {VERSION}   Release Date: {RELEASEDATE}   
            Your current run mode is {RUN_MODE}.
        """
        + COLOR_RESET
    )



def menu():
    """ 显示菜单并处理用户输入 """
    # options = {
    #     "1": lambda: check_devices(auto_match, "🔍 开始自动匹配..."),
    # }

    while True:
        if RUN_MODE == "ONLINE":
            print(COLOR_GREEN + """
                请选择要执行的操作：
                1. 开始巡检
                2. 查看支持的设备制造商
                q. 退出
                """ + COLOR_RESET)
        elif RUN_MODE == "OFFLINE":
            COLOR_YELLOW + "⚠️ 警告：当前运行模式为离线模式，将仅使用本地表内commands进行匹配。" + COLOR_RESET
            print(COLOR_GREEN + """
                请选择要执行的操作：
                1. 开始巡检 (自动匹配Excel当中的command列)
                q. 退出""" + COLOR_RESET)
        
        choice = input(COLOR_YELLOW + "请输入选项，默认1 (1/2/q): " + COLOR_RESET).strip().lower()

        if choice == "q":
            print(COLOR_RED + "程序已退出。" + COLOR_RESET)
            break
        elif choice == "1":
            check_devices()
        elif choice == "2" and RUN_MODE == "ONLINE":
            # 请求社区接口获取当前交换机支持列表
            manuf = api_client.getManuf()

            print(COLOR_GREEN + "\n╔═══════════════════════════════════════╗")
            print("║            支持的设备制造商           ║")
            print("╚═══════════════════════════════════════╝" + COLOR_RESET)

            for i, item in enumerate(manuf, start=1):
                name = item.get("name", "")
                mid = item.get("id", "")
                # 可选：将 UUID 中间部分隐藏，保留前后各 4 位，美化显示
                short_id = f"{mid[:6]}...{mid[-6:]}" if len(mid) > 12 else mid

                print(f"{COLOR_GREEN}{i:2d}. {COLOR_RESET}{name:<10}  ({short_id})")

            print()  # 空行


def check_devices():
    """ 通用设备检查函数，执行不同类型的巡检 """
    print(COLOR_BLUE +  "🔍 开始自动匹配..." + COLOR_RESET)
    try:
        targets = read_target_info()
        if not targets:
            print(COLOR_YELLOW + "⚠️ 未找到任何设备信息，请检查目标文件。" + COLOR_RESET)
            return

        for item in targets:
            protocol = (item.get("protocol") or "").upper()
            ip = item.get("ip") or "-"

            if "SSH" in protocol:
                print(f"🖥️ 设备检查 | 协议: SSH    | IP: {ip}")
                query_manuf_command(item, RUN_MODE)
            elif "TELNET" in protocol:
                print(f"🖥️ 设备检查 | 协议: TELNET | IP: {ip}")
                query_manuf_command(item, RUN_MODE)
            else:
                print(f"{COLOR_RED}⚠️ 跳过设备 | 协议不支持: {protocol or 'None'} | IP: {ip}{COLOR_RESET}")

        print(COLOR_GREEN + "✅ 检查完成" + COLOR_RESET)

    except Exception as e:
        print(COLOR_RED + f"❌ 发生错误: {e}" + COLOR_RESET)


if __name__ == "__main__":
    welcome()
    menu()
