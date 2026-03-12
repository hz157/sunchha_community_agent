import os
import platform
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List

from urllib3.exceptions import NotOpenSSLWarning

warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

from utils.config import get_config_value
from cloud import api_client
from engine.inspector import query_manuf_command
from utils.target import read_target_info
from report.generator import build_run_summary_html, write_html, write_pdf_from_text, write_text
from utils.color import *

VERSION = "v1.0.0"
RELEASEDATE = "2025-12-28"
PLATFORM = None
RUN_MODE = get_config_value("run_mode").upper() 


def _get_inspection_concurrency() -> int:
    raw = get_config_value("inspection.concurrency", get_config_value("inspection_concurrency", "1"))
    try:
        value = int(str(raw).strip())
    except Exception:
        value = 1
    return max(1, value)


def _safe_concurrency(requested: int, target_count: int) -> int:
    # 可配置硬上限，默认 20
    max_raw = get_config_value("inspection.max_concurrency", get_config_value("inspection_max_concurrency", "20"))
    try:
        max_limit = int(str(max_raw).strip())
    except Exception:
        max_limit = 20
    max_limit = max(1, max_limit)

    cpu_count = os.cpu_count() or 1
    cpu_suggested_limit = max(2, cpu_count * 4)
    final_limit = min(max_limit, cpu_suggested_limit, max(1, target_count))
    return max(1, min(requested, final_limit))


def _inspect_one_device(item: Dict[str, Any], run_mode: str, run_id: str) -> Dict[str, Any]:
    protocol = (item.get("protocol") or "").upper()
    ip = item.get("ip") or "-"

    if "SSH" in protocol:
        print(f"🖥️ 设备检查 | 协议: SSH    | IP: {ip}")
        return query_manuf_command(item, run_mode, run_id=run_id)
    if "TELNET" in protocol:
        print(f"🖥️ 设备检查 | 协议: TELNET | IP: {ip}")
        return query_manuf_command(item, run_mode, run_id=run_id)

    print(f"{COLOR_RED}⚠️ 跳过设备 | 协议不支持: {protocol or 'None'} | IP: {ip}{COLOR_RESET}")
    return {"ip": ip, "protocol": protocol, "status": "SKIPPED_UNSUPPORTED_PROTOCOL"}
    
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

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        results: List[Dict[str, Any]] = []
        requested_concurrency = _get_inspection_concurrency()
        concurrency = _safe_concurrency(requested_concurrency, len(targets))
        if concurrency < requested_concurrency:
            print(
                COLOR_YELLOW
                + f"⚠️ 并发上限保护已生效: 请求={requested_concurrency}, 实际={concurrency}"
                + COLOR_RESET
            )
        print(COLOR_BLUE + f"⚙️ 并发巡检线程数(生效): {concurrency}" + COLOR_RESET)

        if concurrency == 1:
            for item in targets:
                results.append(_inspect_one_device(item, RUN_MODE, run_id))
        else:
            indexed_results: Dict[int, Dict[str, Any]] = {}
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                future_map = {
                    executor.submit(_inspect_one_device, item, RUN_MODE, run_id): idx
                    for idx, item in enumerate(targets)
                }
                for future in as_completed(future_map):
                    idx = future_map[future]
                    try:
                        indexed_results[idx] = future.result()
                    except Exception as e:
                        target = targets[idx]
                        indexed_results[idx] = {
                            "ip": target.get("ip", "-"),
                            "protocol": (target.get("protocol") or "").upper(),
                            "status": "FAILED",
                            "error": str(e),
                        }
            results = [indexed_results[i] for i in sorted(indexed_results.keys())]

        summary_lines = [
            f"# 本次巡检汇总 - {run_id}",
            "",
            f"- 设备总数: {len(results)}",
            f"- 成功: {len([r for r in results if r.get('status') == 'SUCCESS'])}",
            f"- 连接失败: {len([r for r in results if r.get('status') == 'CONNECTION_FAILED'])}",
            f"- 跳过: {len([r for r in results if str(r.get('status')).startswith('SKIPPED')])}",
            "",
            "## 设备结果",
        ]
        for item in results:
            ai_conclusion = ((item.get("ai_analysis") or {}).get("conclusion")) if isinstance(item, dict) else None
            summary_lines.append(
                f"- `{item.get('ip', '-')}` | {item.get('protocol', '-')} | {item.get('status', '-')}"
                f" | AI结论: {ai_conclusion or '-'}"
            )
        summary_path = os.path.join("output", run_id, "run_summary.md")
        summary_content = "\n".join(summary_lines)
        write_text(summary_path, summary_content)
        write_html(os.path.join("output", run_id, "run_summary.html"), build_run_summary_html(run_id, results))
        write_pdf_from_text(os.path.join("output", run_id, "run_summary.pdf"), summary_content)
        print(COLOR_GREEN + f"📁 本次巡检输出目录: output/{run_id}" + COLOR_RESET)

        print(COLOR_GREEN + "✅ 检查完成" + COLOR_RESET)

    except Exception as e:
        print(COLOR_RED + f"❌ 发生错误: {e}" + COLOR_RESET)


if __name__ == "__main__":
    welcome()
    menu()
