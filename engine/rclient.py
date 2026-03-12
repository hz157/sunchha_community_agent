import paramiko
import time
import re
import logging
import socket
import select
from typing import Optional

PAGE_KEYWORDS = ['More', '--More--', '---- More ----', "Press any key", "继续查看", "下一页"]

def merge_wrapped_lines(text):
    lines = text.splitlines()
    merged = []

    for line in lines:
        if merged and (
            # 如果上一行被截断（无空格结尾）
            re.search(r'[A-Za-z0-9]$', merged[-1]) and
            # 当前行也是字母开头（说明是续行）
            re.search(r'^[A-Za-z]', line)
        ):
            merged[-1] += line   # 拼接成一行
        else:
            merged.append(line)
    return "\n".join(merged)

def ssh_exec_command(ip: str, username: str, password: str, command: str, port: int = 22, timeout: int = 240) -> str:
    output = ""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        # 连接 SSH
        ssh.connect(hostname=ip, port=port, username=username, password=password, allow_agent=False, look_for_keys=False)
    except Exception as e:
        print(f"❌ SSH Error: {e}")
        return "SSH_CONNECTION_FAILED"
    
    try:
        # 激活交互式 shell
        terminal = ssh.invoke_shell()
        terminal.send(f"{command}\n")
        time.sleep(1)  # 初始等待，确保命令开始执行

        start_time = time.time()
        while True:
            # 超时判断
            if time.time() - start_time > timeout:
                logging.error(f"⏳ Timeout reached while executing '{command}' on {ip}.")
                break

            # 读取可用数据
            if terminal.recv_ready():
                received_data = terminal.recv(65535).decode('utf-8', errors='ignore')
                output += received_data

                # 处理分页
                if any(p in received_data for p in PAGE_KEYWORDS):
                    print('Income Pagination Process Func')
                    terminal.send(" ")
                    time.sleep(1)

                    # 删除 output 最后一行中的分页提示
                    output_lines = output.splitlines()

                    if output_lines:
                        last_line = output_lines[-1]
                        # 如果最后一行本身就是分页提示 → 删除
                        if any(p in last_line for p in PAGE_KEYWORDS):
                            output_lines.pop()

                    output = "\n".join(output_lines)
                    continue

            # 短暂等待，减少 CPU 占用
            time.sleep(0.5)

            # 检查是否返回到 CLI 提示符（通常以 `>` 或 `#` 结尾）
            lines = output.strip().splitlines()
            if lines and re.search(r'[>#]\s*$', lines[-1]):
                break

    except Exception as e:
        return output
    finally:
        ssh.close()


    clean_output = merge_wrapped_lines(output)
    return clean_output

def telnet_exec_command(ip: str, username: str, password: str, command: str, port: int = 23, timeout: int = 240) -> str:
    IAC = 255
    DONT = 254
    DO = 253
    WONT = 252
    WILL = 251
    SB = 250
    SE = 240

    def _process_telnet_negotiation(data: bytes, sock: socket.socket) -> bytes:
        cleaned = bytearray()
        i = 0
        while i < len(data):
            b = data[i]
            if b != IAC:
                cleaned.append(b)
                i += 1
                continue

            if i + 1 >= len(data):
                break

            cmd = data[i + 1]
            if cmd == IAC:
                cleaned.append(IAC)
                i += 2
                continue

            if cmd in (DO, DONT, WILL, WONT):
                if i + 2 >= len(data):
                    break
                opt = data[i + 2]
                if cmd == DO:
                    sock.sendall(bytes([IAC, WONT, opt]))
                elif cmd == WILL:
                    sock.sendall(bytes([IAC, DONT, opt]))
                i += 3
                continue

            if cmd == SB:
                se_index = data.find(bytes([IAC, SE]), i + 2)
                if se_index == -1:
                    break
                i = se_index + 2
                continue

            i += 2

        return bytes(cleaned)

    def _recv_some(sock: socket.socket, deadline: float) -> bytes:
        remaining = deadline - time.time()
        if remaining <= 0:
            return b""
        readable, _, _ = select.select([sock], [], [], min(0.5, remaining))
        if not readable:
            return b""
        try:
            data = sock.recv(65535)
        except Exception:
            return b""
        if not data:
            return b""
        return _process_telnet_negotiation(data, sock)

    def _send_line(sock: socket.socket, s: str) -> None:
        sock.sendall((s + "\n").encode("utf-8", errors="ignore"))

    def _has_prompt(buf: str) -> bool:
        lines = buf.strip().splitlines()
        return bool(lines and re.search(r"[>#]\s*$", lines[-1]))

    output = ""
    sock: Optional[socket.socket] = None
    start_time = time.time()
    try:
        sock = socket.create_connection((ip, port), timeout=min(15, timeout))
        sock.setblocking(False)

        login_buf = ""
        sent_username = False
        sent_password = False
        while True:
            if time.time() - start_time > timeout:
                logging.error(f"⏳ Timeout reached while logging in on {ip}.")
                return "TELNET_CONNECTION_FAILED"

            received = _recv_some(sock, start_time + timeout)
            if received:
                login_buf += received.decode("utf-8", errors="ignore")

            tail = login_buf[-300:]
            if (not sent_username) and re.search(r"(username|login)[: ]*$", tail, flags=re.IGNORECASE):
                _send_line(sock, username)
                sent_username = True
                continue

            if (not sent_password) and re.search(r"password[: ]*$", tail, flags=re.IGNORECASE):
                _send_line(sock, password)
                sent_password = True
                continue

            if _has_prompt(login_buf):
                break

        # 进入特权模式，不然什么都干不了
        _send_line(sock, 'enable')
        time.sleep(1)

        _send_line(sock, command)
        time.sleep(1)

        while True:
            if time.time() - start_time > timeout:
                logging.error(f"⏳ Timeout reached while executing '{command}' on {ip}.")
                break

            received = _recv_some(sock, start_time + timeout)
            if received:
                received_text = received.decode("utf-8", errors="ignore")
                output += received_text

                if any(p in received_text for p in PAGE_KEYWORDS):
                    print('Income Pagination Process Func')
                    sock.sendall(b" ")
                    time.sleep(0.5)

                    output_lines = output.splitlines()
                    if output_lines:
                        last_line = output_lines[-1]
                        if any(p in last_line for p in PAGE_KEYWORDS):
                            output_lines.pop()
                    output = "\n".join(output_lines)
                    continue

            time.sleep(0.2)

            if _has_prompt(output):
                break

    except Exception as e:
        print(f"❌ TELNET Error: {e}")
        return "TELNET_CONNECTION_FAILED"
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

    clean_output = merge_wrapped_lines(output)
    return clean_output
