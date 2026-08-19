/**
 * ⭐ Week 2 完整版：天气 + 计算器 智能助手
 *
 * 这是在 agent-start.js（单工具教学版）之上的完整版：
 *   1. 两个工具：calculator（本地计算）+ get_weather（Open-Meteo 免费 API）
 *   2. 完整 Agent Loop：while 循环，直到 LLM 不再调用工具
 *   3. 带系统提示词：赋予模型角色 + 工具使用规则
 *   4. 最大轮数硬限制（防死循环烧钱，Week 1 重点护栏）
 *
 * 运行: npm start  （或在 node agent.js <你的问题>）
 */

process.loadEnvFile?.();

const BASE_URL = process.env.API_BASE_URL;
const MODEL    = process.env.API_MODEL;
const API_KEY  = process.env.API_KEY;

if (!API_KEY || !BASE_URL) {
  console.error('❌ 缺少配置：请复制 .env.example 为 .env 并填写 API_KEY / API_BASE_URL');
  process.exit(1);
}

// ───────────────────── 1. 系统提示词 ─────────────────────
// 告诉模型：你是谁、能做什么、边界在哪（Week 1 提到的护栏之一）
const SYSTEM_PROMPT = `你是一个智能助手，能使用工具解决用户问题。
可用的工具：
- calculator：四则运算
- get_weather：查询任意城市实时天气（用英文城市名查）

使用规则：
1. 当问题需要计算时，必须用 calculator，不要自己心算
2. 当问题涉及天气时，必须用 get_weather 获取数据后再回答
3. 工具结果只信真实的返回值，不要编造数据
4. 如果工具返回错误信息，如实告诉用户出了什么问题`;

// ───────────────────── 2. 工具定义（JSON Schema）─────────────────────
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
  },
  {
    type: 'function',
    function: {
      name: 'get_weather',
      description: '查询指定城市的实时天气（温度、天气状况、风速）',
      parameters: {
        type: 'object',
        properties: {
          city: { type: 'string', description: '城市英文名，如 Beijing, Shanghai, New York' }
        },
        required: ['city']
      }
    }
  }
];

// ───────────────────── 3. 工具的真实实现 ─────────────────────
// ⚠️ 核心心法（Week 1 强调）：模型只决定「调哪个、传什么参」
//    真正执行的永远是这一份代码。

const FUNCTION_MAP = {
  calculator: ({ a, b, op }) => {
    const ops = { '+': (x, y) => x + y, '-': (x, y) => x - y, '*': (x, y) => x * y, '/': (x, y) => x / y };
    if (!ops[op]) throw new Error(`不支持的运算符: ${op}`);
    if (op === '/' && b === 0) throw new Error('除数不能为 0');
    return { expression: `${a} ${op} ${b}`, result: ops[op](a, b) };
  },

  // Open-Meteo：免费、无需 key。步骤：
  // 1) 城市名 → 经纬度（Open-Meteo 的地理编码接口）
  // 2) 经纬度 → 天气数据（forecast 接口）
  get_weather: async ({ city }) => {
    // 城市 → 经纬度
    const geoUrl = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=1&language=zh`;
    const geoRes = await fetch(geoUrl);
    if (!geoRes.ok) throw new Error(`地理编码失败: ${geoRes.status}`);
    const geo = await geoRes.json();
    if (!geo.results?.length) throw new Error(`找不到城市: ${city}`);

    const { latitude, longitude, name } = geo.results[0];

    // 经纬度 → 天气（current = 当前天气，后续可加 daily=7日预报）
    const wxUrl = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,weather_code,wind_speed_10m&timezone=auto`;
    const wxRes = await fetch(wxUrl);
    if (!wxRes.ok) throw new Error(`天气查询失败: ${wxRes.status}`);
    const wx = await wxRes.json();

    // weather_code 是 WMO 标准码，转成中文描述
    const codeMap = {
      0:'晴', 1:'大部晴朗', 2:'多云', 3:'阴',
      45:'雾', 48:'冻雾', 51:'毛毛雨', 61:'小雨', 63:'中雨', 65:'大雨',
      80:'阵雨', 95:'雷雨', 96:'雷雨伴冰雹'
    };
    const c = wx.current;

    return {
      city: name,
      temperature_c: c.temperature_2m,
      condition: codeMap[c.weather_code] ?? `代码${c.weather_code}`,
      wind_speed_kmh: c.wind_speed_10m,
      observed_at: c.time
    };
  }
};

// ───────────────────── 4. 一次 LLM 调用 ─────────────────────
async function chat(messages) {
  const res = await fetch(`${BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${API_KEY}` },
    body: JSON.stringify({ model: MODEL, messages, tools: TOOLS })
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`API ${res.status}: ${txt.slice(0, 300)}`);
  }
  const data = await res.json();
  return data.choices[0].message;
}

// ───────────────────── 5. Agent Loop（核心）─────────────────────
async function runAgent(userMsg, maxTurns = 6) {
  // 历史消息：系统提示词 + 用户问题
  const messages = [
    { role: 'system', content: SYSTEM_PROMPT },
    { role: 'user', content: userMsg }
  ];

  console.log(`🤖 收到: "${userMsg}"\n`);
  let turn = 0;

  while (turn < maxTurns) {
    turn++;
    console.log(`———— 第 ${turn} 轮 ————`);

    // STEP-A: 把全部历史发给 LLM，看它想干什么
    const reply = await chat(messages);

    // 情况1：LLM 不再要工具 → 输出最终答案，循环结束
    if (!reply.tool_calls?.length) {
      console.log(`✅ 模型认为信息足够，最终回答:\n${reply.content}\n`);
      return reply.content;
    }

    // 情况2：LLM 要调用工具 → 逐个执行
    for (const call of reply.tool_calls) {
      const { name, arguments: argsStr } = call.function;
      let args;
      try {
        args = JSON.parse(argsStr);
      } catch {
        args = {}; // 模型有时会返回坏 JSON，别让整个循环崩掉
      }

      console.log(`🔧 调用工具: ${name}(${JSON.stringify(args)})`);
      let output;
      try {
        // 真正的执行！调用本地函数（async 工具也支持）
        output = await FUNCTION_MAP[name](args);
        console.log(`   ↳ 返回: ${JSON.stringify(output).slice(0, 200)}`);
      } catch (err) {
        // ⚠️ 错误也塞回循环 —— 这就是 Week 1 讲的「纠错靠错误回环」
        output = { error: err.message };
        console.log(`   ↳ 工具报错: ${err.message}`);
      }

      // 把「助手要调工具」 + 「工具结果」都追加进历史，供下一轮 LLM 看到
      messages.push(reply);                          // role=assistant, 含 tool_calls
      messages.push({
        role: 'tool',
        tool_call_id: call.id,
        content: JSON.stringify(output)
      });
    }
  }

  console.log('⛔ 达到最大轮数，强制停止（护栏生效，防止死循环烧钱）');
  return undefined;
}

// ───────────────────── 6. 入口 ─────────────────────
// 支持: node agent.js "北京今天天气"
//       node agent.js "帮我算 (8+5)*12/3"
const question = process.argv[2] ?? '查询北京今天的天气，然后用计算器算一下你看天气时的心情指数（满分100，晴+30，雨-20，多云0），告诉我结果';

runAgent(question).catch((e) => { console.error('💥', e.message); process.exit(1); });