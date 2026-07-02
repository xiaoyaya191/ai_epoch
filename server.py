#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Epoch - Flask Web 服务
纯 AI 聊天，无 Agent/工具操控
"""

import os, sys, json, yaml, ssl, traceback, httpx
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

# ============================================================
# 配置管理
# ============================================================

CONFIG_PATH = Path(__file__).parent / "data" / "config.yaml"
DEFAULT_CONFIG = {
    "ai": {
        "api_base": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini"
    },
    "port": 8766
}

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
            elif isinstance(v, dict):
                for kk, vv in v.items():
                    if kk not in cfg[k]:
                        cfg[k][kk] = vv
        return cfg
    return dict(DEFAULT_CONFIG)

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

config = load_config()

# ============================================================
# AI 后端
# ============================================================

class AIBackend:
    """AI 后端 — 调用 OpenAI 兼容 API"""

    def __init__(self, api_base: str, api_key: str, model: str):
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.model = model

    def chat(self, messages: list, temperature: float = 0.7,
             max_tokens: int = 4096) -> str:
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        resp = httpx.post(url, json=payload, headers=headers, timeout=120)
        if resp.status_code != 200:
            raise Exception(f"API error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def list_models(self) -> list[dict]:
        """获取可用模型列表"""
        url = f"{self.api_base}/models"
        req = Request(url, headers={
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "ai_epoch/1.0",
        })
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=15, context=ctx) as resp:
            data = json.loads(resp.read())
        raw = data.get("data", data if isinstance(data, list) else [])
        models = []
        skip_kw = ["embed", "moderation", "dall-e", "tts", "whisper", "audio", "image", "video", "realtime"]
        for m in raw:
            mid = m.get("id", "") if isinstance(m, dict) else str(m)
            if not mid:
                continue
            low = mid.lower()
            if any(kw in low for kw in skip_kw):
                continue
            models.append({"id": mid, "owned_by": m.get("owned_by", "") if isinstance(m, dict) else ""})
        models.sort(key=lambda x: x["id"])
        return models

# ============================================================
# 聊天管理
# ============================================================

SYSTEM_PROMPT = """你是 AI Epoch，一个智能 AI 助手。

## 回复要求
- 简洁清晰，结构化呈现
- 重要信息放在最前面
- 使用标题、列表、表格等格式
- 主动帮助用户解决问题

## 当前环境
- 当前时间: {time}

## 推荐追问
每次回复末尾必须附带 2-3 条推荐追问或操作建议，用以下格式输出（方便前端渲染为可点击按钮）：
---SUGGESTIONS---
- 简洁的推荐追问1（每条不超过30字）
- 简洁的推荐追问2
- 简洁的推荐追问3

要求：必须严格使用 ---SUGGESTIONS--- 作为分隔标记，每条建议独立一行以 "- " 开头，建议要与当前对话内容相关。"""

class ChatSession:
    """聊天会话管理"""

    def __init__(self):
        self.messages: list = []
        self._init_system()

    def _init_system(self):
        sys_prompt = SYSTEM_PROMPT.format(
            time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        self.messages = [{"role": "system", "content": sys_prompt}]

    def send(self, user_input: str, ai: AIBackend) -> dict:
        self.messages.append({"role": "user", "content": user_input})
        try:
            reply = ai.chat(self.messages)
            self.messages.append({"role": "assistant", "content": reply})
            return {"reply": reply, "history_length": len(self.messages)}
        except Exception as e:
            return {"error": str(e)}

    def reset(self):
        self.messages = []
        self._init_system()

    def get_history(self) -> list:
        return [m for m in self.messages if m["role"] != "system"]


_ai: AIBackend = None
_session: ChatSession = None

def get_ai() -> AIBackend:
    global _ai, config
    if _ai is None:
        cfg_ai = config.get("ai", {})
        _ai = AIBackend(
            api_base=cfg_ai.get("api_base", ""),
            api_key=cfg_ai.get("api_key", ""),
            model=cfg_ai.get("model", "gpt-4o-mini")
        )
    return _ai

def get_session() -> ChatSession:
    global _session
    if _session is None:
        _session = ChatSession()
    return _session

def reset_all():
    global _ai, _session
    _ai = None
    _session = None


# ============================================================
# API 路由
# ============================================================

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/api/status')
def api_status():
    cfg_ai = config.get("ai", {})
    return jsonify({
        "status": "running",
        "model": cfg_ai.get("model", ""),
        "api_configured": bool(cfg_ai.get("api_key", "")),
        "time": datetime.now().isoformat()
    })


@app.route('/api/models/list')
def api_models_list():
    """从配置的 API 端点获取可用模型列表"""
    cfg_ai = config.get("ai", {})
    api_key = cfg_ai.get("api_key", "")
    api_base = cfg_ai.get("api_base", "")
    if not api_key or not api_base:
        return jsonify({"ok": False, "message": "请先配置 API Key 和地址", "models": []})
    try:
        ai = get_ai()
        models = ai.list_models()
        return jsonify({"ok": True, "models": models, "count": len(models)})
    except Exception as e:
        return jsonify({"ok": False, "message": f"获取失败: {str(e)}", "models": [], "error": str(e)})


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    global config

    if request.method == 'GET':
        safe = json.loads(json.dumps(config))
        if 'ai' in safe and 'api_key' in safe['ai']:
            key = safe['ai']['api_key']
            if key:
                safe['ai']['api_key'] = key[:8] + '***' + key[-4:] if len(key) > 12 else '***'
        return jsonify(safe)

    data = request.get_json() or {}
    for k, v in data.items():
        if k in config:
            if isinstance(config[k], dict) and isinstance(v, dict):
                config[k].update(v)
            else:
                config[k] = v

    save_config(config)
    reset_all()
    return jsonify({"result": "ok"})


@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json() or {}
    user_input = data.get("message", "").strip()
    reset = data.get("reset", False)

    if not user_input:
        return jsonify({"error": "message is required"}), 400

    try:
        ai = get_ai()
        session = get_session()

        if reset:
            session.reset()

        result = session.send(user_input, ai)
        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()[-500:]
        }), 500


@app.route('/api/history')
def api_history():
    session = get_session()
    return jsonify({"history": session.get_history()})


@app.route('/api/reset', methods=['POST'])
def api_reset():
    session = get_session()
    session.reset()
    return jsonify({"result": "ok"})


# ============================================================
# 启动
# ============================================================

def main():
    port = config.get("port", 8766)
    print(f"AI Epoch Server starting on http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, debug=False)


if __name__ == "__main__":
    main()
