from imaplib import Commands
import os
from cloud.api_client import *
from report.generator import write_to_txt
from engine.rclient import ssh_exec_command, telnet_exec_command
from utils.color import *



def execute_commands(device, commands):
    """
    执行指定设备的命令列表，并将每条命令的回显输出保存到本地文件。

    此方法依次通过 SSH 执行传入的命令列表。每个命令项应为一个包含 'command' 字段的字典。
    执行成功后，会在 output/<设备IP>/ 目录下创建以命令名命名的 .txt 文件保存回显内容。
    若 SSH 连接失败，将立即停止对该设备的后续命令执行。

    Args:
        device (dict):
            设备信息字典，包含以下字段：
                - ip (str): 设备 IP 地址  
                - username (str): SSH 登录用户名  
                - password (str): SSH 登录密码  
                - port (int): SSH 端口号  

        commands (list[dict]):
            需要执行的命令项列表。
            每个元素格式示例：
                {
                    "command": "display version"
                }
            若某项中 command 为空，将自动跳过。

    Behavior:
        - 使用 ssh_exec_command() 执行命令。
        - 若返回 "SSH_CONNECTION_FAILED"，立即终止该设备的命令执行。
        - 为每条命令创建文件：./output/<设备IP>/<command>.txt
        - 在终端打印执行状态和错误信息。

    Notes:
        - 命令文本用于文件名，因此包含特殊字符（如 '/', '\\', '|', '*' 等）可能导致文件写入失败。
        - 若写入文件失败，方法会提示错误，但不会中断整体执行流程。
        - 该函数为操作类函数，不返回数据。

    Exceptions:
        - 捕获所有执行过程中的异常并打印，不向上抛出异常。
        - 单条命令的异常不会影响下一条命令的执行（除连接失败情况外）。

    Returns:
        None
    """
    for item in commands:
        command = item['command']
        if not command:
            continue  # 跳过空行

        try:
            # 通知用户当前执行的命令
            print(f"{COLOR_BLUE}🚀 正在执行命令: {command} on {device.get('ip')}{COLOR_RESET}")

            protocol = (device.get("protocol") or "").upper()
            exec_func = telnet_exec_command if "TELNET" in protocol else ssh_exec_command

            data = exec_func(
                ip=device.get("ip"),
                username=device.get("username"),
                password=device.get("password"),
                command=command,
                port=device.get("port")
            )

            if data in {"SSH_CONNECTION_FAILED", "TELNET_CONNECTION_FAILED"}:
                print(f"{COLOR_RED}❌ 设备 {device.get('ip')} 连接失败，跳过当前设备{COLOR_RESET}")
                return

            # 构造文件路径（例如：./output/192.168.1.1/display version.txt）
            output_dir = os.path.join("output", device.get("ip"))
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, f"{command}.txt")

            # 写入文件
            if write_to_txt(file_path=file_path, content=data):
                print(f"{COLOR_GREEN}✅ {device.get('ip')} 执行 {command} 回显已写入文件：{file_path}{COLOR_RESET}")
            else:
                print(f"{COLOR_RED}❌ {device.get('ip')} 执行 {command} 回显写入失败：{file_path}{COLOR_RESET}")

        except Exception as e:
            print(f"{COLOR_RED}❌ 设备 {device.get('ip')} 执行 {command} 发生错误: {e}{COLOR_RESET}")


def query_manuf_command(device):
    """检查设备品牌并执行默认命令"""
    target = (device.get("manuf") or "").upper()
    # 从社区数据库中获取品牌
    manuf = getManufByName(target)
    # 数据库中查找不到的品牌，直接报错返回
    if not manuf:
        print(f"{COLOR_RED}⚠️ 设备品牌 {device.get('manuf')} 不存在{COLOR_RESET}")
        return


    commands = getCommand(manuf_id=manuf.get("id"))
    if not commands:
        print(f"{COLOR_RED}⚠️ 设备品牌 {manuf.get('en_name')} 没有配置命令，跳过{COLOR_RESET}")
        return
    execute_commands(device, commands)
    return
    