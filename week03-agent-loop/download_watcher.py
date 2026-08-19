"""
⭐ Week 3 扩展: 下载文件夹自动归类守护程序（混合模式）

模式: 规则优先 + LLM 兜底
  ① watchdog 监听下载目录
  ② 新文件 => 先按扩展名规则归类（毫秒级、免费、断网可用）
  ③ 规则没命中 => 调 LLM 判断该归哪类

使用:
  python download_watcher.py                 # 默认监听 ~/Downloads
  python download_watcher.py D:/某个目录      # 指定目录

安全设计：
  - 只处理【新出现】的文件，绝不动老文件
  - 忽略浏览器临时下载文件（.crdownload/.part/.tmp）
  - 移动先建目录，跨盘符用 shutil 复制后删除（保证安全）
"""

import os, sys, json, time, shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ───────────────────── 一、配置 ─────────────────────
API_KEY   = os.environ.get("API_KEY", "")
BASE_URL  = os.environ.get("API_BASE_URL", "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1")
MODEL     = os.environ.get("API_MODEL", "qwen3.8-max")

# 默认监听下载目录
TARGET_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Downloads")

if not API_KEY:
    # 兜底: 读 week02 的 .env
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "week02-tool-use", ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.strip().split("=", 1)
                os.environ[k] = v
        API_KEY = os.environ.get("API_KEY", "")
if not API_KEY:
    sys.exit("❌ 缺少 API_KEY：设置环境变量或先完成 week02 的 .env 配置")

# ───────────────────── 二、规则层（毫秒级、零成本）─────────────────────
# 扩展名 → 目标文件夹
RULES = {
    # 图片
    ".jpg": "图片", ".jpeg": "图片", ".png": "图片", ".gif": "图片",
    ".bmp": "图片", ".svg": "图片", ".webp": "图片", ".ico": "图片",
    # 视频
    ".mp4": "视频", ".avi": "视频", ".mkv": "视频", ".mov": "视频",
    ".flv": "视频", ".wmv": "视频", ".webm": "视频",
    # 音频
    ".mp3": "音乐", ".wav": "音乐", ".flac": "音乐", ".aac": "音乐",
    ".ogg": "音乐", ".m4a": "音乐",
    # 文档
    ".pdf": "文档", ".doc": "文档", ".docx": "文档", ".txt": "文档",
    ".md": "文档", ".odt": "文档", ".rtf": "文档", ".tex": "文档",
    # 表格
    ".xls": "表格", ".xlsx": "表格", ".csv": "表格", ".ods": "表格",
    # 演示
    ".ppt": "演示文稿", ".pptx": "演示文稿", ".key": "演示文稿",
    # 代码
    ".py": "代码", ".js": "代码", ".ts": "代码", ".java": "代码",
    ".c": "代码", ".cpp": "代码", ".h": "代码", ".html": "代码",
    ".css": "代码", ".json": "代码", ".sh": "代码", ".go": "代码",
    ".rs": "代码", ".php": "代码", ".ipynb": "代码",
    # 压缩包
    ".zip": "压缩包", ".rar": "压缩包", ".7z": "压缩包",
    ".tar": "压缩包", ".gz": "压缩包", ".bz2": "压缩包",
    # 安装包
    ".exe": "安装包", ".msi": "安装包", ".dmg": "安装包",
    # 设计文件
    ".psd": "设计", ".ai": "设计", ".fig": "设计", ".sketch": "设计",
}

# 永远忽略的临时文件/系统文件
IGNORE_EXTS = {".crdownload", ".part", ".tmp", ".temp", ".download", ".crdownload"}
IGNORE_NAMES = {"desktop.ini", "thumbs.db"}


def rule_lookup(filename):  # 规则层：命中返回文件夹名，未命中返回 None
    ext = os.path.splitext(filename)[1].lower()
    if ext in RULES:
        return RULES[ext]
    return None


# ───────────────────── 三、LLM 兜底层 ─────────────────────
def llm_classify(filename):
    """规则没命中时问 LLM：这个文件该放哪个文件夹？"""
    import urllib.request, urllib.error
    SYSCFG = ("你是文件分类专家。用户给你一个文件名/未知类型文件，"
              "你决定它该放进哪个分类文件夹。"
              "只输出文件夹名，不要解释。若实在无法判断，输出'其他'。")
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSCFG},
            {"role": "user", "content": f"文件: {filename}  该放入哪一类？"},
        ],
        # ⚠ qwen 默认 thinking 模式：不支持 tool_choice=object/required，此处留空让模型自由
    }).encode()
    req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            msg = json.loads(r.read().decode())["choices"][0]["message"]
        # 模型可能调工具，也可能直接文字回答（thinking 下常见）
        if msg.get("tool_calls"):
            fn = msg["tool_calls"][0]["function"]
            folder = json.loads(fn["arguments"]).get("folder")
            if folder:
                return folder
        content = (msg.get("content") or "").strip()
        # 从文字里抠出文件夹名（去掉标点、第 1 个词）
        import re
        words = re.split(r"[，。\s、,.:：]", content)
        for w in words:
            if w and len(w) <= 6:
                return w
        return "其他"
    except Exception as e:
        print(f"   ⚠ LLM 兜底失败({e})，放'其他'")
        return "其他"


# ───────────────────── 四、核心移动逻辑 ─────────────────────
def classify_and_move(filepath):
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filename)[1].lower()

    # 防御: 忽略临时/系统文件
    if ext in IGNORE_EXTS or filename.lower() in IGNORE_NAMES:
        print(f"  ⏭ 跳过临时文件: {filename}")
        return

    foldername = rule_lookup(filename)

    if foldername:
        src = "规则"               # 第一层: 规则命中, 零成本
    else:
        foldername = llm_classify(filename)   # 第二层: LLM 兜底
        src = "LLM"
    if not foldername:
        foldername, src = "其他", "LLM"

    target_dir = os.path.join(TARGET_DIR, foldername)
    dest = os.path.join(target_dir, filename)

    if os.path.normpath(filepath) == os.path.normpath(dest):
        return  # 已在目标位置

    try:
        os.makedirs(target_dir, exist_ok=True)
        # 跨盘符用 shutil, 同盘用 rename（更快）
        if os.path.dirname(os.path.abspath(filepath))[0] != os.path.dirname(os.path.abspath(target_dir))[0]:
            shutil.move(filepath, dest)
        else:
            os.rename(filepath, dest)
        print(f"  ✅ [{src}] {filename} → {foldername}/")
    except Exception as e:
        print(f"  ❌ 移动失败 {filename}: {e}")


# ───────────────────── 五、watchdog 监听 ─────────────────────
class DownloadHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            self.process(event.src_path)

    def process(self, path):
        # 稍等文件写完（浏览器下载常分段写）
        deadline = time.time() + 30
        prev_size = -1
        while time.time() < deadline:
            try:
                size = os.path.getsize(path)
            except OSError:
                break
            if size == prev_size and size > 0:
                break  # 大小稳定 = 下载完成
            prev_size = size
            time.sleep(1)
        classify_and_move(path)


def main():
    os.makedirs(TARGET_DIR, exist_ok=True)
    print(f"👀 监听中: {TARGET_DIR}")
    print(f"   规则 {len(RULES)} 种类型 + LLM 兜底（Ctrl+C 停止）\n")

    handler = DownloadHandler()
    obs = Observer()
    obs.schedule(handler, TARGET_DIR, recursive=False)  # 不递归, 只监听本级
    obs.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()


if __name__ == "__main__":
    main()