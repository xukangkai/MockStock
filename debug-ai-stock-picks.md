# Debug Session: ai-stock-picks

Status: [OPEN]

## Symptom
用户反馈：AI 好像一直没有选股。需要判断是行情数据问题导致选不出来，还是代码逻辑问题。

## Hypotheses
1. 行情源返回为空或关键字段缺失，导致候选池为空。
2. 候选筛选条件过严，行情正常但全部被过滤。
3. AI/LLM 配置不可用或调用失败，导致选股步骤跳过或失败。
4. 前端未展示已生成的选股结果，后端实际有数据。
5. 非交易时间/运行模式逻辑阻止了选股或开仓决策。

## Evidence Log

### 接口证据
- `/api/engine/status` 返回：`ai_configured: true`，说明 AI 配置可用。
- `/api/agent/status` 返回：Agent 正在运行，市场分析师、风控等节点已执行。
- `/api/agent/status` 中 `researcher` 节点：`thinking: "无候选标的，跳过筛选"`，`result: "本轮无合适候选"`。
- `/api/agent/cycles?limit=5` 中最近多轮 `plan.buy_picks: []`，reasoning 多次出现“候选猎手无推荐标的/无候选标的”。
- `/api/picks` 返回 `[]`，与 Agent 最新推荐为空一致。

### 代码证据
- `build_agent_cycle_context()` 写入候选池的 key 是 `candidate_pool`。
- `run_candidate_research_node()` 读取候选池的 key 是 `candidates`。
- `_build_agent_thinking()` 也读取 `ctx.get("candidates", [])`，因此 UI 上也会显示 0 只候选。
- `_comprehensive_trade()` 确实构建了 `candidates_ctx`，并传给 `build_agent_cycle_context(..., candidates_ctx=candidates_ctx, ...)`。

## Conclusion
根因更像是代码问题：候选池字段名不一致，导致行情获取后构建出的候选池没有被候选猎手节点读取。

具体不一致：
- 写入：`candidate_pool`
- 读取：`candidates`

建议最小修复：让读取侧兼容 `candidate_pool`，或在上下文构建时同时写入 `candidates`。
