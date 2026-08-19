/**
 * ⭐ Week 2 教学版：跑通「第一个 function calling」
 *
 * 目标：亲眼看到 Agent Loop 的三步
 *   1. LLM 决定调用工具 → 返回结构化 tool_calls
 *   2. 我们的代码真正执行函数 → 拿到结果
 *   3. 把结果塞回对话历史 → LLM 给出最终答案
 *
 * 运行: npm run start:teach
 * 配套讲解见 README.md
 */

// ── 第 0 步：加载配置 ──────────────────────────────────────────
// Node 20+ 原生支持从 .env 加载（不用装 dotenv）
process.loadEnvFile?.();

const BASE_URL = process.env.API_BASE_URL;
const MODEL    = process.env.API_MODEL;
const API_KEY  = process.env.API_KEY;

if (!API_KEY || !BASE_URL) {
  console.error('❌ 缺少配置：请先复制 .env.example 为 .env 并填写 API_KEY / API_BASE_URL');
  process.exit(1);
}

// ── 第 1 步：定义工具（工具 = 我们的代码，模型只负责选）──
const TOOLS = [
  {
    type: 'function',
    function: {
      name: 'calculator',
      description: '四则运算计算器，支持 + - * /',
      parameters: {
        type: 'object',
        properties: {
          a: { type: 'number', description: '第一个数' },
          b: { type: 'number', description: '第二个数' },
          op: { type: 'string', enum: ['+', '-', '*', '/'], description: '运算符' }
        },
        required: ['a', 'b', 'op']
      }
    }
  }
];

// 工具的真实实现 —— 真正执行的代码在这
const FUNCTION_MAP = {
  calculator: ({ a, b, op }) => {
    const ops = { '+': (x, y) => x + y, '-': (x, y) => x - y, '*': (x, y) => x * y, '/': (x, y) => x / y };
    if (!ops[op]) throw new Error(`不支持的运算符: ${op}`);
    if (op === '/' && b === 0) throw new Error('除数不能为 0');
    const result = ops[op](a, b);
    // ⚠️ 工具返回结果严格来说得是字符串（模型只读文本）
    return { expression: `${a} ${op} ${b}`, result };
  }
};

// ── 第 2 步：封装一次 LLM 调用 ─────────────────────────────────
async function chat(messages) {
  const res = await fetch(`${BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`
    },
    body: JSON.stringify({ model: MODEL, messages, tools: TOOLS })
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  const data = await res.json();
  return data.choices[0].message;
}

// ── 第 3 步：主循环（最简版：最多转 2 轮）─────────────────────
async function main() {
  // 对话历史从用户的「问题」开始
  const messages = [{ role: 'user', content: '请用计算器工具计算 97 * 13 等于多少？' }];

  console.log('🟦 Step 1 → 发给 LLM');
  const reply = await chat(messages);
  console.log(JSON.stringify(reply.tool_calls, null, 2));

  for (const call of reply.tool_calls ?? []) {
    const { name, arguments: args } = call.function;
    console.log(`\n🟩 Step 2 → 执行工具 ${name}(${JSON.stringify(JSON.parse(args))})`);
    const output = FUNCTION_MAP[name](JSON.parse(args));
    // 工具的名字 + 结果，追加进历史
    messages.push(reply);
    messages.push({ role: 'tool', tool_call_id: call.id, content: JSON.stringify(output) });
  }

  console.log('\n🟨 Step 3 → 把结果塞回历史，再问一次');
  const final = await chat(messages);
  console.log(`模型最终回答：${final.content}`);
}

main().catch((e) => { console.error('💥', e.message); process.exit(1); });