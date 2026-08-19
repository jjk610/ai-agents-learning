# Week 3 — 手写 Agent Loop（文件整理 Agent）✅

> 日期：2026-08-19
> 核心周 ⭐：不用任何框架，纯 Python 实现 Agent 循环
> 前置：Week 2 的工具调用循环 + Week 1 的 Agent Loop 理论

## 任务
不依赖任何 Agent SDK，手写一个文件整理 Agent：
**自己探索目录 → 自己规划分类 → 自己执行整理 → 自己反思复查 → 总结收工**

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