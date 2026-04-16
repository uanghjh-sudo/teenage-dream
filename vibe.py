# 屏蔽所有无关警告
import warnings
warnings.filterwarnings("ignore")

# 1. 先导入依赖 + 初始化 Flask（必须写在最前面！）
from flask import Flask, request, render_template_string, redirect, url_for
import json
import os
import jieba
import docx
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
DB_FILE = "library.json"

# 2. 再定义所有函数和路由
# 初始化空库
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False)

def load_lib():
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_lib(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def split_sentences(text):
    text = text.strip()
    for sep in ["。", "！", "？", "…", "\n", "\r"]:
        text = text.replace(sep, "|")
    sentences = [s.strip() for s in text.split("|") if s.strip() and len(s) > 4]
    return sentences

def auto_tags(sentence):
    words = [w for w in jieba.lcut(sentence) if len(w) >= 2]
    return list(set(words))[:6]

def read_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

# 删除功能
@app.route("/delete/<int:idx>")
def delete(idx):
    lib = load_lib()
    if 0 <= idx < len(lib):
        del lib[idx]
        save_lib(lib)
    return redirect(url_for("index"))

# 主页（修复了 enumerate 问题）
@app.route("/")
def index():
    lib = load_lib()
    q = request.args.get("q", "").strip()
    res = []
    if q:
        q = q.lower()
        for item in lib:
            if q in item["content"].lower() or q in "|".join(item.get("tags", [])).lower():
                res.append(item)
    return render_template_string('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文案搜索库</title>
    <style>
        * {box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, -apple-system, sans-serif;}
        body {max-width: 800px; margin: 0 auto; padding: 30px 20px; background: #fafafa;}
        .card {background: white; border-radius: 16px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.04);}
        input, textarea, button {width: 100%; padding: 14px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 12px; font-size: 15px;}
        button {background: #222; color: white; border: none; font-weight: 500; cursor: pointer;}
        button:hover {background: #333;}
        .item {padding: 16px; background: #f7f7f7; border-radius: 12px; margin-bottom: 10px;}
        .tags {color: #888; font-size: 13px; margin-top: 8px;}
        h1 {font-size: 24px; margin-bottom: 20px;}
        h3 {font-size: 18px; margin: 0 0 14px 0;}
        .tip {background: #e6f7ff; padding: 12px 16px; border-radius: 12px; margin-bottom: 20px; font-size: 15px; color: #0066cc;}
        .del-btn {display: inline-block; margin-top: 10px; padding: 6px 12px; background: #ff4d4f; color: white; border-radius: 8px; font-size: 12px; border: none; cursor: pointer; text-decoration: none;}
    </style>
</head>
<body>
    <h1>文案搜索库</h1>

    <div class="card">
        <form><input name="q" placeholder="搜索关键词..." value="{{q}}"></form>
    </div>

    {% if q and res %}
    <div class="tip">🔽 搜索完成，请<strong>下滑查看结果</strong></div>
    {% endif %}

    <div class="card">
        <h3>单条添加</h3>
        <form action="/add" method="post">
            <textarea name="content" rows="3" placeholder="输入文案内容"></textarea>
            <input name="tags" placeholder="关键词（逗号分隔，留空自动识别）">
            <button type="submit">添加文案</button>
        </form>
    </div>

    <div class="card">
        <h3>批量导入（TXT / Word）</h3>
        <form action="/batch" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".txt,.docx">
            <button type="submit">上传并自动分句+打标签</button>
        </form>
    </div>

    <div class="card">
        <h3>从网页获取文案</h3>
        <form action="/fetch" method="post">
            <input name="url" placeholder="输入文章网址">
            <button type="submit">抓取正文</button>
        </form>
    </div>

    {% for item in res %}
    <div class="item">
        {{ item.content }}
        {% if item.tags %}
        <div class="tags">{{ item.tags|join(' · ') }}</div>
        {% endif %}
        <a href="/delete/{{ loop.index0 }}" class="del-btn" onclick="return confirm('确定删除这条文案？')">🗑️ 删除</a>
    </div>
    {% endfor %}
</body>
</html>
''', q=q, res=res)

# 添加文案
@app.route("/add", methods=["POST"])
def add():
    content = request.form.get("content", "").strip()
    tags_str = request.form.get("tags", "").strip()
    if not content:
        return "<script>alert('请输入文案内容'); history.back();</script>"
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else auto_tags(content)
    lib = load_lib()
    lib.append({"content": content, "tags": tags})
    save_lib(lib)
    return "<script>alert('添加成功！'); location.href='/';</script>"

# 批量导入
@app.route("/batch", methods=["POST"])
def batch():
    file = request.files.get("file")
    if not file:
        return "<script>alert('请选择文件'); history.back();</script>"
    try:
        filename = file.filename.lower()
        if filename.endswith(".txt"):
            text = file.read().decode("utf-8")
        elif filename.endswith(".docx"):
            text = read_docx(file)
        else:
            return "<script>alert('仅支持TXT/DOCX格式'); history.back();</script>"
        sentences = split_sentences(text)
        lib = load_lib()
        for s in sentences:
            lib.append({"content": s, "tags": auto_tags(s)})
        save_lib(lib)
        return f"<script>alert('导入成功！共{len(sentences)}句文案'); location.href='/';</script>"
    except Exception as e:
        return f"<script>alert('导入失败：{str(e)}'); history.back();</script>"

# 网页抓取
@app.route("/fetch", methods=["POST"])
def fetch():
    url = request.form.get("url", "").strip()
    if not url:
        return "<script>alert('请输入网址'); history.back();</script>"
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")
        body = soup.find("body").get_text(strip=True, separator="\n")
        sentences = split_sentences(body)
        lib = load_lib()
        for s in sentences:
            lib.append({"content": s, "tags": auto_tags(s)})
        save_lib(lib)
        return f"<script>alert('抓取完成！共{len(sentences)}句文案'); location.href='/';</script>"
    except Exception as e:
        return f"<script>alert('抓取失败：{str(e)}'); history.back();</script>"

# 3. 最后才是启动代码
if __name__ == "__main__":
    print("\n=== 文案搜索库已启动 ===")
    print("本地访问地址：http://127.0.0.1:5001")
    print("如需公网访问，请在新终端执行：cd ~/Desktop && ./ngrok http 5001")
    print("========================\n")
    app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=False)
