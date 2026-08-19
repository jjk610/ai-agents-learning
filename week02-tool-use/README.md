# Week 2 — Tool Use（Function Calling）✅

> 日期：2026-08-19
> 前置：Week 1 的四个核心概念（尤其 Tool Use / Agent Loop）
> 厂商无关实现：OpenAI 兼容协议 + 阿里云百炼（DashScope）qwen3.8-max

## 任务
用大模型 API 实现**天气查询 + 计算器助手**，理解 Function Calling 完整流程。

## 文件结构

```
week02-tool-use/
├── .env              # 环境变量（已被 .gitignore 忽略，含 API_KEY ⚠️ 勿提交）
├── .env.example      # 环境变量模板
├── agent-start.js    # ⭐ 教学版：单工具，每步打印，看懂最小流程
├── agent.js          # ⭐ 完整版：双工具（计算器+天气），多轮 Agent Loop
└── README.md         # 本文档（讲解）
```

## 运行方法

```bash
# 0) 配置（如果还没有 .env）
cp .env.example .env   # 然后填入 API_KEY（百炼控制台获取）

# 1) 教学版 —— 看最小流程
npm run start:teach

# 2) 完整版 —— 带参数提问
npm start
node agent.js "计算 (8+5)*12/3"
node agent.js "北京今天天气怎么样？"
node agent.js "查上海天气，然后算温差"
```

## 核心概念：Function Calling 到底怎么回事

### 一句话
> **模型（大脑）决定"调哪个工具、传什么参数"，我们的代码（手脚）真正执行。**

模型本身**不联网、不执行任何函数**——它只会"说"一段结构化 JSON，表示"我想调用 `calculator({a:97,b:13,op:'*'})`"。然后由我们的程序接住这个意图，去执行真的函数，再把结果**喂回**给模型。

### 完整流程（4 步）

```
用户: "97*13 等于多少?"
   │
   ▼
① 发送 [系统提示 + 用户问题 + 工具定义TOOLS] 给 LLM
   │
   ▼
② LLM 返回（不是答案，而是"我要调工具"）:
   {"name":"calculator","arguments":"{\"a\":97,\"b\":13,\"op\":\"*\"}"}
   │
   ▼
③ 我们的代码执行 calculator(97,13,"*") → 1261
   │
   ▼
④ 把工具名+结果追加进对话历史，再次发送给 LLM
   这次 LLM 看到结果，给出最终答案: "97 × 13 = 1261"
```

### 工具定义（TOOLS）是什么

TOOLS 数组是给模型看的"功能菜单"，用 **JSON Schema**（字段声明格式）描述：

```json
{
  "type": "function",
  "function": {
    "name": "calculator",                    // 工具名（模型会记住）
    "description": "四则运算计算器",           // ⭐ 作用说明（模型靠它决定何时用）
    "parameters": {
      "type": "object",
      "properties": {
        "a": { "type": "number" },           // 参数声明
        "op": { "type": "string", "enum": ["+","-","*","/"] }  // 枚举限定
      },
      "required": ["a", "b", "op"]           // 必填项
    }
  }
}
```

⚠️ **工具的 description 质量直接决定模型选得准不准**——Week 1 说的"工具设计至关重要"。

### Agent Loop 在这个项目里的体现

```js
while (turn < maxTurns) {
  reply = await chat(messages);         // ① 发历史给 LLM
  if (!reply.tool_calls) break;         // ② 没要工具 → 输出答案，退出
  for (call of reply.tool_calls) {
    output = await FUNCTION_MAP[name](args);  // ③ 执行真实的函数
    messages.push(...{ tool: output });       // ④ 结果塞回历史
  }
}
```

- **多步计算** `(8+5)*12/3` → 循环 3 次，每次算一步，把中间结果累积进历史（13 → 156 → 52）
- **护栏**：`maxTurns=6`，防止模型失控死循环烧钱（Week 1 重点）

## 两个踩坑记录（复盘用）

### 1. 工具执行要能容错
模型有时会返回坏 JSON 或调不存在的工具。代码里对 `JSON.parse` 和 `FUNCTION_MAP[name]` 都做了 try/catch，错误信息会**塞回循环**让模型自己看到并重新决策——这就是 Week 1 讲的"错误回环纠错"。

### 2. power: 天气的"城市名→坐标"是**两级调用**
Open-Meteo 免费 API 分两步：
1. 地理编码：`geocoding-api.open-meteo.com/v1/search?name=北京` → 返回经纬度
2. 天气数据：`api.open-meteo.com/v1/forecast?latitude=..&longitude=..` → 返回温度/天气码

模型只需要说"查北京天气"，工具内部自动完成两步——**工具封装复杂度，让接口对模型保持简单**（Week 1 的"精心设计工具"）。

### 3. 天气码 weather_code 是 WMO 标准
数字 0/1/2/3 数字化不好看，代码里做了"码→中文"映射（0=晴, 61=小雨…），模型直接用中文回答，用户体验好很多。

## 验收清单

- [x] 教学版看懂最小 function calling 流程
- [x] 完整版：计算器工具（多步运算）
- [x] 完整版：天气工具（Open-Meteo 真实数据）
- [x] 双工具协作（查天气 + 算温差）
- [x] 错误回环（工具容错 + 模型感知）
- [x] 最大轮数护栏

## 下一步
Week 3 要**手写 Agent Loop**（不用任何 SDK），到时候你能把 `agent.js` 里的循环拆出来，加上"规划 + 反思"，就是一个真正可用的通用 Agent 骨架了 💪