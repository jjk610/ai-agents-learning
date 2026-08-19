# Week 3 — 手写 Agent Loop（文件整理 Agent）✅

> 日期：2026-08-19
> 核心周 ⭐：不用任何框架，纯 Python 实现 Agent 循环
> 前置：Week 2 的工具调用循环 + Week 1 的 Agent Loop 理论

## 任务
不依赖任何 Agent SDK，手写一个文件整理 Agent：
**自己探索目录 → 自己规划分类 → 自己执行整理 → 自己反思复查 → 总结收工**

## 📦 两个程序

| 文件 | 作用 | 模式 |
|------|------|------|
| `agent.py` | 手写 Agent Loop：一次性整理指定目录 | 交互式（LLM 全程决策） |
| `download_watcher.py` | **下载文件夹自动归类守护程序** | 混合模式（规则优先 + LLM 兜底）|

## 为什么这是「核心周」

| | Week 2（工具调用） | Week 3（真 Agent） |
|---|---|---|
| 模型行为 | 按需调用工具（被动） | 自己决策全流程（主动） |
| 决策依据 | 用户每步指挥 | 自己 explore → plan → act → reflect |
| 循环结构 | while + 工具执行 | while + **规划/反思**塞回历史 |
| 心智模型 | Function Calling | **ReAct 雏形**（Reasoning + Acting）|

**一句话：Week 2 教模型"用工具"，Week 3 教模型"自己决定怎么用工具、并检查用得对不对"。**

## 文件与运行

```
week03-agent-loop/
├── agent.py      # ⭐ 手写 Agent Loop（约 200 行）
├── sandbox/      # 测试目录（15 个混合文件）
└── README.md
```

```bash
# 运行（会读取 week02 的 .env 里的 API key；也可自己设 API_KEY）
cd ~/ai-agents-learning/week03-agent-loop
python agent.py "整理这个目录里的所有文件，把它们按类型归类"
```

## 四个新增能力（这是 Agent 的内核）

```
用户任务
   │
   ▼ ┌───────────────────────────────────┐
   └─▶│ ① 探索环境 list_files             │
      │ ② 自主规划 make_dir ×N            │← 看到文件 → 定分类
      │ ③ 执行整理 move_file ×N           │← 逐个归位
      │ ④ 反思复查 list_files             │← 检查有没有漏
      └───────────────────────────────────┘
         │ 干净了 → done(summary) 收工
         │ 还有漏 → 回到 ①（下一轮）
```

- **① 探索**：模型必须自己先 `list_files` 看目录，而不是瞎规划
- **② 规划**：模型根据实际文件内容，动态决定建哪些文件夹（我们的案例是 6 类）
- **③ 执行**：批量 move_file，一次处理 15 个
- **④ 反思**：完成后再 `list_files` 复查根目录 + 各子目录 = 确认无遗漏

## 代码结构（对照理解）

```python
SYSTEM_PROMPT ← 角色 + 规则（先探索、自由定制分类、完成后复查、用相对路径）
TOOLS         ← JSON Schema 描述 4 个工具（list_files/make_dir/move_file/done）
FUNCTION_MAP  ← ❗ 真正执行的代码（安全校验：禁止越权访问目录外）
chat()        ← 一次 LLM 调用（OpenAI 兼容协议）
run_agent()   ← 主循环：while turn < MAX_TURNS
                  发历史 → 看 tool_calls → 逐个执行 → 结果塞回历史
```

## 三个关键设计点（踩坑总结）

### 1. `done` 工具 = 显式的结束信号
```
Week 2 的写法：         模型"不调工具了" = 结束（隐式，靠猜）
Week 3 的写法：         模型必须显式调用 done 才是正常收工
```
好处：把"结束"从**被动判断**变成**模型主动汇报**，避免模型忘了下结论就停。
（若想训练"循环型"行为，保留显式 done 是可复现的关键。）

### 2. 安全护栏：工具不能越权
```python
if not (src.startswith(os.path.abspath(WORK_DIR)) and dst.startswith(...)):
    return {"error": "禁止越权访问目录外部"}
```
模型可能传 `../../`，工具必须校验路径在工作目录内。这也是 Week 1 强调的护栏落地。

### 3. 错误回环依然在
```python
try:
    result = FUNCTION_MAP[name](**args)
except TypeError as e:
    result = {"error": ...}   # 错误塞回历史 → 模型自己 next step
```
工具执行出错（如源文件不存在）= 返回值带着 `error` 塞回循环，模型看了自己调整。

## 本次真实运行记录（完整）

```
Turn 1  list_files                → 看到 15 个文件
Turn 2  make_dir ×6               → 建 文档/图片/代码/表格/演示文稿/压缩包
Turn 3  move_file ×15             → 全部归位
Turn 4  list_files(根)+ list_files(每个子目录) → 复查，确认无遗漏
Turn 5  done(总结)                → 收工：15 文件 → 6 文件夹，0 遗漏
```

运行前/后文件系统核对：
- ✅ 根目录 0 个散落文件
- ✅ 15 个文件全部进入对应分类文件夹
- ✅ 中文文件名、多类型（.py/.json/.txt/.doc/.docx/.xlsx/.pptx/.jpg/.png/.gif/.zip）全部正确处理

## 验收清单

- [x] 手写 Agent Loop（不依赖任何框架）
- [x] 四能力：探索/规划/执行/反思 完整闭环
- [x] 真实运行：15 文件自动整理为 6 类，0 遗漏
- [x] 显式 done 收工信号
- [x] 路径越权安全校验
- [x] 最大轮数护栏 + 错误回环

## 下一步
这个 Agent 已经很接近「真 Agent」结构了。Week 8 用框架（LangGraph / Claude Agent SDK）重写它时，你会发现框架就是把这套 while 循环 + 工具 + 状态管理封装成了方便组件。
也可以先自己扩展玩法：让它支持二级分类（如 文档/合同 vs 文档/笔记）、按文件名关键词分类、或生成整理报告文件。

---

# 🔧 扩展：下载文件夹自动归类守护程序（download_watcher.py）

> 让"从网上下载的文件"下载完成即自动归类，不用手动整理。

## 设计：混合模式（规则优先 + LLM 兜底）

```
[浏览器] 下载新文件 → Downloads/
       │  (watchdog 监听文件系统事件)
       ▼
┌─────────────────────────────┐
│ ① 规则层（毫秒级、免费、断网可用） │
│    .jpg/.png  → 图片/         │
│    .pdf/.doc  → 文档/         │
│    .exe/.msi  → 安装包/       │
│    ... 命中 → 直接移动 ✅      │
└──────────────┬──────────────┘
               │ 没命中规则？
               ▼
┌─────────────────────────────┐
│ ② LLM 兜底层                 │
│    qwen 判断"这文件该放哪"     │
│    → 返回文件夹名 → 移动        │
└─────────────────────────────┘
```

**为什么混合？** 按扩展名规则覆盖 90% 常见类型（零成本），只有生僻类型才让 LLM 判断——符合 Anthropic「能固定就不用 Agent」的工程原则。

## 运行

```bash
pip install watchdog          # 第一次需要
python download_watcher.py                 # 默认监听 ~/Downloads
python download_watcher.py D:/某个目录       # 指定目录
```

Ctrl+C 停止。放后台运行: `python download_watcher.py` 放到一个终端挂着即可。

## 内置规则表（可自行增删）

| 分类 | 扩展名 |
|------|--------|
| 图片 | .jpg .jpeg .png .gif .bmp .svg .webp .ico |
| 视频 | .mp4 .avi .mkv .mov .flv .wmv .webm |
| 音乐 | .mp3 .wav .flac .aac .ogg .m4a |
| 文档 | .pdf .doc .docx .txt .md .odt .rtf .tex |
| 表格 | .xls .xlsx .csv .ods |
| 演示文稿 | .ppt .pptx .key |
| 代码 | .py .js .ts .java .c .cpp .h .html .css .json .sh .go .rs .php .ipynb |
| 压缩包 | .zip .rar .7z .tar .gz .bz2 |
| 安装包 | .exe .msi .dmg |
| 设计 | .psd .ai .fig .sketch |

## 安全设计（重要）

1. **只处理新出现的文件** —— 绝不动你已有的老文件（watchdog 监听的是 on_created 事件）
2. **忽略浏览器临时文件** —— `.crdownload` / `.part` / `.tmp`（下载中不误动）
3. **等下载完成再动** —— 连续 1 秒文件大小不变才判定写完，避免移动半截文件
4. **跨盘符安全移动** —— 用 shutil.move 而非 os.rename，失败不丢数据

## 真实测试结果

模拟"浏览器下载"4 个文件到监听目录，全部自动归位：

```
📥 旅行照片.jpg   → ✅ [规则] 图片/
📥 项目预案.pdf   → ✅ [规则] 文档/
📥 动画演示.mov   → ✅ [规则] 视频/
📥 神秘备份.rxk   → ✅ [LLM] 备份/   ← 规则不认识，LLM 兜底归为备份
```

## 遇到的坑（复盘）

**qwen thinking 模式不支持 tool_choice=object/required。** 第一次用 `tool_choice` 强制模型调 classify 工具时返回 400。解决：去掉 tool_choice，让模型自由发挥，代码同时解析「工具调用」和「纯文字回答」两种返回。这是国产模型与 GPT/Claude 的差异点之一，值得记住。