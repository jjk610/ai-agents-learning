"""
⭐ Week 3: 手写 Agent Loop —— 文件整理 Agent（不用任何框架）

与 Week 2 的根本区别：
  Week 2 agent.js  -> 模型"按需调用工具"（被动）
  Week 3 agent.py  -> 模型"自己探索 -> 自己规划 -> 自己执行 -> 自己反思"（主动）

四个新增能力（这是真正的 Agent 内核）：
  1. 探索环境  : list_files 先看目录里有什么
  2. 自主规划  : 根据看到的文件类型，自己决定建哪几个文件夹
  3. 执行整理  : make_dir + move_file 逐个归位
  4. 反思查漏  : 再 list_files 看一遍，确认全部归位，才调用 done 结束

运行: python agent.py "整理 sandbox/ 目录"
"""

import os, json, sys, datetime

# Windows 控制台默认 GBK，无法打印 emoji → 强制 UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ───────────────────── 配置 ─────────────────────
BASE_URL = os.environ.get("API_BASE_URL", "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1")
MODEL    = os.environ.get("API_MODEL", "qwen3.8-max")
API_KEY  = os.environ.get("API_KEY", "")
MAX_TURNS = 20   # 护栏：最多循环多少轮（Week 1 重点）

if not API_KEY:
    # 兜底：从 week2 的 .env 读 key（复用）
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "week02-tool-use", ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.strip().split("=", 1)
                os.environ[k] = v
        API_KEY = os.environ.get("API_KEY", "")

if not API_KEY:
    sys.exit("❌ 缺少 API_KEY：请设置环境变量或先完成 week02 的 .env 配置")

# 工作目录 = agent.py 所在目录下的 sandbox/
WORK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandbox")

# ───────────────────── 一、系统提示词 ─────────────────────
SYSTEM_PROMPT = f"""你是一个【文件整理 Agent】。你的工作目录是 {WORK_DIR}。

你的任务：把工作目录里的杂文件归到合适的分类文件夹里。

【重要规则】
1. 先调用 list_files 查看目录里有什么，再规划分类方案
2. 必须自己建分类文件夹（make_dir），把文件移进去（move_file）
3. 合理的分类示例：文档/图片/代码/表格/演示文稿/压缩包，但你可以根据实际文件**自由定制**
4. 完成后必须再调用 list_files 检查一遍，确认没有遗漏
5. 全部整理妥当后，调用 done 工具汇报总结，结束任务

【工具使用规范】
- 用相对路径操作（如 "图片/全家福.jpg" 或 "全家福.jpg"），不要用绝对路径
- 不要移动/删除任何以 . 开头的隐藏文件
"""

# ───────────────────── 二、工具定义 ─────────────────────
TOOLS = [
    {"type": "function", "function": {
        "name": "list_files",
        "description": "列出工作目录下的所有文件（也可以是子目录）",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string", "description": "子目录路径，默认留空表示根目录"}},
                       "required": []}}},
    {"type": "function", "function": {
        "name": "make_dir",
        "description": "创建一个新目录",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string", "description": "要创建的目录路径，如 图片"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "move_file",
        "description": "把文件从 source 移动到 destination（两个都是相对路径）",
        "parameters": {"type": "object",
                       "properties": {"source": {"type": "string", "description": "源文件相对路径"},
                                      "destination": {"type": "string", "description": "目标路径，如 图片/全家福.jpg"}},
                       "required": ["source", "destination"]}}},
    {"type": "function", "function": {
        "name": "done",
        "description": "所有整理工作完成，汇报总结并结束任务",
        "parameters": {"type": "object",
                       "properties": {"summary": {"type": "string", "description": "整理结果总结"}},
                       "required": ["summary"]}}},
]

# ───────────────────── 三、工具实现 ─────────────────────
def tool_list_files(path=""):
    target = os.path.join(WORK_DIR, path) if path else WORK_DIR
    if not os.path.isdir(target):
        return {"error": f"目录不存在: {path or '(根)'}"}
    items = os.listdir(target)
    files, dirs = [], []
    for it in items:
        full = os.path.join(target, it)
        (dirs if os.path.isdir(full) else files).append(it)
    return {"目录": sorted(dirs), "文件": sorted(files), "共": len(items)}

def tool_make_dir(path):
    target = os.path.normpath(os.path.join(WORK_DIR, path))
    if not target.startswith(os.path.abspath(WORK_DIR)):
        return {"error": "禁止越权访问目录外部"}
    os.makedirs(target, exist_ok=True)
    return {"ok": True, "已创建": path}

def tool_move_file(source, destination):
    src = os.path.normpath(os.path.join(WORK_DIR, source))
    dst = os.path.normpath(os.path.join(WORK_DIR, destination))
    # 安全校验：只允许在工作目录内移动
    if not (src.startswith(os.path.abspath(WORK_DIR)) and dst.startswith(os.path.abspath(WORK_DIR))):
        return {"error": "禁止越权移动文件"}
    if not os.path.isfile(src):
        return {"error": f"源文件不存在: {source}"}
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.rename(src, dst)
    return {"ok": True, "已移动": f"{source} → {destination}"}

def tool_done(summary):
    # 收工信号：返回一个特殊标记，主循环看到就退出
    return {"__DONE__": True, "总结": summary}

FUNCTION_MAP = {
    "list_files": tool_list_files,
    "make_dir":   tool_make_dir,
    "move_file":  tool_move_file,
    "done":       tool_done,
}

# ───────────────────── 四、LLM 调用 ─────────────────────
def chat(messages):
    import urllib.request, urllib.error
    payload = json.dumps({"model": MODEL, "messages": messages, "tools": TOOLS}).encode()
    req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())["choices"][0]["message"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API {e.code}: {e.read().decode()[:200]}")

# ───────────────────── 五、Agent 主循环 ⭐ ─────────────────────
def run_agent(user_msg):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    print(f"🤖 {user_msg}\n")

    for turn in range(1, MAX_TURNS + 1):
        print(f"—— Turn {turn}/{MAX_TURNS} ——")
        reply = chat(messages)

        # 没有工具调用 → 模型直接说了（可能忘了 done），把它当 завершение
        if not reply.get("tool_calls"):
            print(f"✅ 模型直接回复（未调 done）:\n{reply.get('content')}\n")
            return

        # 执行本轮所有工具调用
        for call in reply["tool_calls"]:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}

            print(f"🔧 {name}({json.dumps(args, ensure_ascii=False)})")
            try:
                result = FUNCTION_MAP[name](**args)
            except TypeError as e:
                result = {"error": f"参数不对: {e}"}
            print(f"   ↳ {json.dumps(result, ensure_ascii=False)[:180]}")

            # 关键：工具实际上也可能 throw，统一包成 {error}（Week 1 的错误回环）
            if isinstance(result, dict) and result.get("__DONE__"):
                print(f"\n🎉 完成! {result['总结']}")
                return

            # 把「助手调用」「工具结果」追加进历史
            messages.append(reply)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})

    print("⛔ 达到最大轮数，强制停止")

# ───────────────────── 六、入口 ─────────────────────
if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "整理这个目录里的所有文件，把它们按类型归类"
    # 运行前拍照（整理后对比用）
    before = set(os.listdir(WORK_DIR)) if os.path.isdir(WORK_DIR) else set()
    run_agent(task)