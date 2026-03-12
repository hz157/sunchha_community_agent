import os
import re
from datetime import datetime
from typing import Any, Dict, List

from cloud.api_client import getCommand, getManufByName
from cloud.ai_analysis import analyze_inspection_result, is_ai_enabled
from cloud.webhook_client import notify_inspection_result
from engine.rclient import ssh_exec_command, telnet_exec_command
from report.generator import build_device_report_html, write_html, write_json, write_pdf_from_text, write_text
from utils.color import COLOR_BLUE, COLOR_GREEN, COLOR_RED, COLOR_YELLOW, COLOR_RESET


def _safe_filename(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "_", name).strip() or "empty_command"


def _device_run_dir(run_id: str, ip: str) -> str:
    return os.path.join("output", run_id, "devices", ip)


def _build_device_report(result: Dict[str, Any]) -> str:
    command_lines: List[str] = []
    for item in result.get("command_results", []):
        status = "成功" if item.get("success") else "失败"
        command_lines.append(f"- [{status}] `{item.get('command')}` -> {item.get('file_path')}")

    ai_data = result.get("ai_analysis") or {}
    ai_block = [
        f"- 状态: {'成功' if ai_data.get('success') else '未执行/失败'}",
        f"- 平台: {ai_data.get('provider', '-')}",
        f"- 结论: {ai_data.get('conclusion', '-')}",
        f"- 风险等级: {ai_data.get('risk_level', '-')}",
    ]
    if ai_data.get("analysis"):
        ai_block.append(f"- 分析: {ai_data.get('analysis')}")
    if ai_data.get("suggestions"):
        ai_block.append(f"- 建议: {'; '.join(ai_data.get('suggestions'))}")
    if ai_data.get("error"):
        ai_block.append(f"- 错误: {ai_data.get('error')}")

    command_section = command_lines or ["- 无命令执行结果"]
    return "\n".join(
        [
            f"# 巡检报告 - {result.get('ip')}",
            "",
            "## 基础信息",
            f"- 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- IP: {result.get('ip')}",
            f"- 协议: {result.get('protocol')}",
            f"- 厂商: {result.get('manuf')}",
            f"- 结果: {result.get('status')}",
            "",
            "## 命令执行",
            *command_section,
            "",
            "## AI 分析",
            *ai_block,
            "",
        ]
    )


def _run_device_command(device: Dict[str, Any], command: str) -> str:
    protocol = (device.get("protocol") or "").upper()
    exec_func = telnet_exec_command if "TELNET" in protocol else ssh_exec_command
    return exec_func(
        ip=device.get("ip"),
        username=device.get("username"),
        password=device.get("password"),
        command=command,
        port=device.get("port"),
    )


def _parse_offline_commands(device: Dict[str, Any]) -> List[Dict[str, str]]:
    # 兼容不同列名：command / commands / cmd
    raw = device.get("command")
    if raw in (None, ""):
        raw = device.get("commands")
    if raw in (None, ""):
        raw = device.get("cmd")
    if raw is None:
        return []

    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return []

    normalized = text.replace("，", ",").replace("\n", ",")
    return [{"command": item.strip()} for item in normalized.split(",") if item.strip()]


def execute_commands(device: Dict[str, Any], commands: List[Dict[str, str]], run_id: str) -> Dict[str, Any]:
    ip = device.get("ip") or "unknown_ip"
    protocol = (device.get("protocol") or "").upper()
    device_dir = _device_run_dir(run_id, ip)
    command_dir = os.path.join(device_dir, "commands")
    os.makedirs(command_dir, exist_ok=True)

    result: Dict[str, Any] = {
        "run_id": run_id,
        "ip": ip,
        "protocol": protocol,
        "manuf": device.get("manuf") or "-",
        "status": "SUCCESS",
        "command_results": [],
        "raw_output": "",
        "device_dir": device_dir,
    }

    raw_blocks: List[str] = []
    for item in commands:
        command = (item.get("command") or "").strip()
        if not command:
            continue

        print(f"{COLOR_BLUE}🚀 正在执行命令: {command} on {ip}{COLOR_RESET}")
        data = _run_device_command(device, command)
        if data in {"SSH_CONNECTION_FAILED", "TELNET_CONNECTION_FAILED"}:
            print(f"{COLOR_RED}❌ 设备 {ip} 连接失败，跳过当前设备{COLOR_RESET}")
            result["status"] = "CONNECTION_FAILED"
            break

        safe_name = _safe_filename(command)
        command_file_path = os.path.join(command_dir, f"{safe_name}.txt")
        saved = write_text(file_path=command_file_path, content=data)
        result["command_results"].append(
            {
                "command": command,
                "success": saved,
                "file_path": command_file_path,
            }
        )

        if saved:
            raw_blocks.append(f"## {command}\n{data}")
            print(f"{COLOR_GREEN}✅ {ip} 执行 {command} 回显已写入文件：{command_file_path}{COLOR_RESET}")
        else:
            print(f"{COLOR_YELLOW}⚠️ {ip} 执行 {command} 回显为空或写入失败：{command_file_path}{COLOR_RESET}")

    result["raw_output"] = "\n\n".join(raw_blocks)
    write_text(os.path.join(device_dir, "raw_output.txt"), result["raw_output"])
    return result


def _commands_from_device(device: Dict[str, Any], run_mode: str) -> List[Dict[str, str]]:
    if run_mode == "OFFLINE":
        return _parse_offline_commands(device)

    target = (device.get("manuf") or "").upper()
    manuf = getManufByName(target)
    if not manuf:
        return []
    return getCommand(manuf_id=manuf.get("id")) or []


def query_manuf_command(device: Dict[str, Any], run_mode: str = "ONLINE", run_id: str = "") -> Dict[str, Any]:
    if not run_id:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    commands = _commands_from_device(device, run_mode)
    if not commands:
        ip = device.get("ip") or "unknown_ip"
        if run_mode == "OFFLINE":
            print(
                f"{COLOR_RED}⚠️ 设备 {ip} 未找到可执行命令，跳过。"
                f"请检查 Excel 列名 `command`（或兼容 `commands/cmd`）及内容是否为逗号分隔命令。{COLOR_RESET}"
            )
        else:
            print(f"{COLOR_RED}⚠️ 设备 {ip} 未找到可执行命令，可能是厂商未匹配或云端命令为空。{COLOR_RESET}")
        return {
            "run_id": run_id,
            "ip": ip,
            "protocol": (device.get("protocol") or "").upper(),
            "manuf": device.get("manuf") or "-",
            "status": "SKIPPED",
            "command_results": [],
            "raw_output": "",
            "device_dir": _device_run_dir(run_id, ip),
        }

    result = execute_commands(device, commands, run_id=run_id)
    ai_result: Dict[str, Any] = {"success": False}
    if is_ai_enabled() and result.get("raw_output"):
        ai_result = analyze_inspection_result(result["raw_output"])

    result["ai_analysis"] = ai_result
    write_json(os.path.join(result["device_dir"], "device_result.json"), result)
    report_content = _build_device_report(result)
    report_md_path = os.path.join(result["device_dir"], "report.md")
    report_pdf_path = os.path.join(result["device_dir"], "report.pdf")
    report_html_path = os.path.join(result["device_dir"], "report.html")
    write_text(report_md_path, report_content)
    write_html(report_html_path, build_device_report_html(result))
    write_pdf_from_text(report_pdf_path, report_content)

    notify_inspection_result(result)
    return result
