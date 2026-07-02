#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Epoch - CLI 终端客户端
纯 AI 聊天，无 Agent/工具操控
"""

import os, sys, io, json, httpx

# UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API = "http://127.0.0.1:8766"
COLORS = {
    "reset": "\033[0m",
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "dim": "\033[2m",
    "bold": "\033[1m",
}

def c(text, color="reset"):
    if os.name == 'nt':
        return text
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def print_banner():
    print()
    print(c("  ╔══════════════════════════════════════╗", "cyan"))
    print(c("  ║         AI Epoch - CLI              ║", "cyan"))
    print(c("  ║      智能 AI 助手 · 命令行版         ║", "dim"))
    print(c("  ╚══════════════════════════════════════╝", "cyan"))
    print()


def print_help():
    print(f"""
{c("命令:", "bold")}
  /help         显示帮助
  /status       查看服务状态
  /reset        重置对话
  /history      查看对话历史
  /config       查看当前配置
  /exit         退出

{c("提示:", "bold")}
  直接输入问题即可与 AI 对话。
  例如：
  - "解释一下量子计算的基本原理"
  - "帮我写一段 Python 排序代码"
  - "推荐几本值得读的书"
""")


def check_server():
    try:
        r = httpx.get(f"{API}/api/status", timeout=3)
        if r.status_code == 200:
            d = r.json()
            status = "就绪" if d.get("api_configured") else "未配置API"
            print(f"{c('✓', 'green')} 服务器在线 ({status}, 模型: {d.get('model', 'N/A')})")
            return True
    except:
        pass
    print(f"{c('✗', 'red')} 无法连接服务器 {API}")
    print(f"  请先启动: {c('python server.py', 'yellow')}")
    return False


def show_status():
    try:
        r = httpx.get(f"{API}/api/status", timeout=5)
        d = r.json()
        print(f"\n{c('服务状态:', 'bold')}")
        print(f"  状态: {c(d.get('status', 'unknown'), 'green')}")
        print(f"  模型: {d.get('model', 'N/A')}")
        print(f"  API配置: {'是' if d.get('api_configured') else c('否', 'red')}")
        print()
    except Exception as e:
        print(f"{c('错误:', 'red')} {e}")


def show_config():
    try:
        r = httpx.get(f"{API}/api/config", timeout=5)
        d = r.json()
        print(f"\n{c('当前配置:', 'bold')}")
        print(json.dumps(d, ensure_ascii=False, indent=2))
        print()
    except Exception as e:
        print(f"{c('错误:', 'red')} {e}")


def show_history():
    try:
        r = httpx.get(f"{API}/api/history", timeout=5)
        d = r.json()
        history = d.get("history", [])
        if not history:
            print(f"\n{c('暂无对话历史', 'dim')}\n")
            return

        print(f"\n{c(f'对话历史 ({len(history)} 条):', 'bold')}")
        for i, msg in enumerate(history):
            role = msg.get("role", "?")
            content = msg.get("content", "")
            role_icon = "👤" if role == "user" else "🤖"
            role_color = "yellow" if role == "user" else "cyan"
            display = content[:120] + "..." if len(content) > 120 else content
            print(f"  {role_icon} {c(f'[{i}]', 'dim')} {c(display, role_color)}")
        print()
    except Exception as e:
        print(f"{c('错误:', 'red')} {e}")


def send_message(text):
    print(f"\n{c('⏳ 思考中...', 'dim')}", end='\r')

    try:
        r = httpx.post(f"{API}/api/chat",
                       json={"message": text},
                       timeout=180)
        d = r.json()
        print(" " * 30, end='\r')

        if d.get("error"):
            print(f"\n{c('✗ 错误:', 'red')} {d['error']}")
            return

        reply = d.get("reply", "")
        print(f"\n{c('AI:', 'cyan')}")
        print(reply)
        print()

    except httpx.TimeoutException:
        print(f"\n{c('✗ 请求超时', 'red')}")
    except Exception as e:
        print(f"\n{c('✗ 错误:', 'red')} {e}")


def main():
    print_banner()

    if not check_server():
        sys.exit(1)

    print_help()

    while True:
        try:
            user_input = input(c("\n> ", "green")).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{c('再见！', 'cyan')}")
            break

        if not user_input:
            continue

        if user_input.startswith('/'):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == '/exit' or cmd == '/quit':
                print(f"{c('再见！', 'cyan')}")
                break
            elif cmd == '/help':
                print_help()
            elif cmd == '/status':
                show_status()
            elif cmd == '/config':
                show_config()
            elif cmd == '/history':
                show_history()
            elif cmd == '/reset':
                httpx.post(f"{API}/api/reset", timeout=5)
                print(f"\n{c('✓ 对话已重置', 'green')}\n")
            else:
                print(f"{c(f'未知命令: {cmd}', 'red')}")
        else:
            send_message(user_input)


if __name__ == "__main__":
    main()
