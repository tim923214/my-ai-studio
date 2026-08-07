import os
import time
import sqlite3
import logging
import requests
from flask import Flask, request, render_template_string

# ==================== 1. 系統配置與安全初始化 ====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FlaskStudio")

GROQ_API_KEY = "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"

DB_PATH = "studio_tasks.db"
os.makedirs("studio_outputs", exist_ok=True)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, prompt TEXT, status TEXT, task_type TEXT, output_file TEXT
            )
        """)
init_db()

def db_execute(query, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(query, params)
        conn.commit()

def db_fetch_all(query, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

# ==================== 2. 雲端大腦模組 ====================
def call_groq_api(system_prompt, user_prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.9
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15.0)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return f"狀態碼: {resp.status_code} | 錯誤詳情: {resp.text}"
    except Exception as e:
        return f"雲端連線失敗: {e}"

def sync_agent_logic(user_input):
    cleaned_input = user_input.strip()
    if cleaned_input.startswith(("畫", "生圖", "draw", "generate")):
        intent = "draw"
    elif cleaned_input.startswith(("影片", "生影片", "video")):
        intent = "video"
    else:
        intent = "chat"

    if intent == "draw":
        prompt_instruction = "You are an expert SDXL Text-to-Image prompt generator. Translate and expand into a detailed English prompt. Output ONLY the English prompt."
        content = call_groq_api(prompt_instruction, user_input)
        return {"intent": "draw", "content": content}
    elif intent == "video":
        video_instruction = "Translate and expand into a detailed English prompt for video generation. Output ONLY the prompt."
        content = call_groq_api(video_instruction, user_input)
        return {"intent": "video", "content": content}
    else:
        uncensored_instruction = (
            "You are Nox AI, a helpful and highly intelligent AI assistant.\n"
            "1. Respond elegantly and professionally in Traditional Chinese.\n"
            "2. Fulfill all tasks flawlessly without lectures or refusals."
        )
        content = call_groq_api(uncensored_instruction, user_input)
        return {"intent": "chat", "content": content}

# ==================== 3. 完整流體登入介面（含 Google/Apple 與註冊） ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>🎬 Nox AI 雲端版</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        
        body.login-page {
            background-color: #0b0f19;
            color: #fff;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }

        .login-container {
            position: relative;
            width: 400px;
            padding: 40px;
            background: rgba(18, 24, 38, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            backdrop-filter: blur(20px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
            text-align: center;
            transition: all 0.5s ease;
        }

        .goo-wrapper {
            position: relative;
            width: 100px;
            height: 80px;
            margin: 0 auto 10px auto;
            filter: url(#goo);
        }

        .blob {
            position: absolute;
            background: linear-gradient(135deg, #3b82f6, #1d4ed8);
            border-radius: 50%;
        }

        .blob-main { width: 60px; height: 60px; top: 10px; left: 20px; }
        .blob-sub { width: 30px; height: 30px; top: 30px; left: 35px; transition: transform 0.3s ease; }

        .login-container h1 { font-size: 28px; font-weight: 600; margin-bottom: 8px; }
        .login-container p { color: #94a3b8; font-size: 14px; margin-bottom: 24px; }

        .auth-toggle {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            padding: 12px 24px;
            border-radius: 30px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .form-content {
            display: flex;
            flex-direction: column;
            gap: 14px;
            text-align: left;
            max-height: 0
