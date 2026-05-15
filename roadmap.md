# GoTeacher 路线图

## 项目目标

用 KataGo 分析引擎 + LLM 替代人类围棋教师，能回答：
1. 当前局面谁好谁坏，为什么
2. 我应该下哪，为什么
3. 如果我下某个地方，可以吗，为什么
4. 推荐的下法（考虑学生棋力，过于复杂的最优解不推荐）
5. 举一反三，这类局面的通用处理方式

---

## 核心认知：数字不等于教学

KataGo 输出的是**评估结果**，不是**原因**。
- `scoreLoss=4.2, severity=mistake` → 只能说"这手损失了约4目"
- **为什么**损失、**哪里**判断错了、**这类局面**该怎么想——KataGo 完全没有

LLM 有围棋概念知识（布局方向、定式、手筋），缺的是**局面感知能力**——它看不懂坐标列表，需要视觉化的局面表示。

**最高性价比的一步**：棋盘 ASCII 可视化 + 方位语义摘要，让 LLM 能直接"看懂"局面。

---

## 当前 Bug / 必修项

### B1：实战手不在候选列表时评估缺失（P0）
**现象**：`playedMoveEvaluation` 里 `scoreLoss` 为空，`severity` 错误地显示 `excellent`。
**根因**：引擎只搜了 top-N 候选手，实战手 visits 不够没进列表。
**修法**：实战手找不到时，`severity` 改为 `unknown`，`whyInteresting` 加 `played_move_not_in_candidates` 标签。可选：追加一次专门针对实战手的低 visits 补查。

### B2：profile 名称不友好（P1）
**现象**：`--profile 1d` 直接崩，需要传 `rank_1d` 或 `preaz_1d`，用户完全不知道。
**合法格式**：
- `rank_20k` 到 `rank_9d`（现代开局风格）
- `preaz_20k` 到 `preaz_9d`（AlphaZero 前风格）
- `proyear_1800` 到 `proyear_2023`（职业棋手历史年份）
- `rank_{BR}_{WR}`（黑白方不同棋力）
**修法**：CLI 层做映射，`1d` → `rank_1d`，`5k` → `rank_5k`，错误时列出合法格式。

### B3：asyncio 缓冲溢出（P1）
**现象**：开启 `includeMovesOwnership` 时响应超 64KB，`asyncio.StreamReader` 默认 limit 溢出崩溃。
**修法**：`create_subprocess_exec` 加 `limit=2**20`（1MB）。

---

## KataGo 未启用的重要字段

### rootInfo 新字段（目前未透传）

| 字段 | 说明 | 教学用途 |
|------|------|---------|
| `rawVarTimeLeft` | 网络预估"还有多长有意义的对局" | **直接判断布局/中盘/官子阶段**，值~50=布局，~10=中盘，~2=官子 |
| `humanStWrError` | 人类（该棋力段）对局面的短期胜率不确定性 | **复杂度指标**，> 0.06 = 该棋力段难以判断的复杂局面 |
| `humanStScoreError` | 人类对局面的短期目数不确定性 | 复杂度的目数维度 |
| `humanWinrate` | 人类模型预期的胜率 | 对比引擎 winrate，差值大 = 人类会误判这个局面 |
| `humanScoreMean` | 人类模型预期的目数结果 | 同上 |
| `rawWinrate` | 神经网络裸胜率（不搜索） | 对比搜索后 winrate，差距大 = 局面容易误判 |
| `rawStWrError` | 网络自估短期不确定性 | 局面稳定性指标 |
| `symHash` | 局面对称等价哈希 | 定式/相似局面检索的 key |
| `thisHash` | 局面唯一哈希 | 缓存 key，比当前 SHA256 更精确 |

### moveInfos 新字段

| 字段 | 说明 | 教学用途 |
|------|------|---------|
| `pvVisits` | pv 每步的搜索深度 | 衰减越快 = 后续越不确定，复杂度判断 |
| `utility` | 综合胜率+目数的效用值 | 比 winrate 更全面的候选手排序依据 |
| `lcb` | winrate 的置信下界 | 保守估计，visits 少时更可靠 |
| `weight` / `edgeVisits` | 带权重的访问数 | 不确定时权重低，比 visits 更可信 |

### humanPolicy（全盘人类落子概率）

`includePolicy: true` + `humanSLProfile` 时返回，**目前完全没有接入**。

```
humanPolicy top5（rank_1d，第3手后）：
  D16: 0.4687   ← 1d棋手47%会下这里
  D17: 0.3824   ← 38%会下这里
  P4:  0.0379
```

这是 Q2"我应该下哪"的核心数据——覆盖全盘，不只是引擎搜到的候选手。

### humanSL 搜索偏置参数（overrideSettings）

```json
"humanSLRootExploreProbWeightless": 0.5   // 50% playouts探索人类手，不影响评估
"humanSLCpuctPermanent": 2.0              // 确保高人类先验的手有足够visits
```

加上这两个参数后，candidates 里的 `humanPrior` 覆盖更全面（否则人类可能下但引擎不搜的手没有数据）。

---

## 新增功能规划

### F1：`board_render` / `--format board`（最高优先级）

输出棋盘 ASCII + 方位语义，让 LLM 直接"看懂"局面：

```
当前局面（第3手，轮到白棋）：

   A B C D E F G H J K L M N O P Q R S T
19 . . . . . . . . . . . . . . . . . . .
18 . . . . . . . . . . . . . . . . . . .
17 . . . . . . . . . . . . . . . . . . .
16 . . . . . . . . . . . . . . . ● . . .
 4 . . . ○ . . . . . . . . . . . . . . .
 3 . . . . . . . . . . . . . . . . ● . .

阶段：布局（rawVarTimeLeft=51）
形势：均衡，白方微领 1.0 目
黑棋落子：R4（右下，小目方向）
引擎最优：D16（左上小目），1d人类概率 47%
复杂度：中等（humanStWrError=0.048）
```

### F2：`position_summary`（结构化语义摘要）

在 `AnalysisResult` 里加一个 `summary` 字段，把所有数字聚合成 LLM 可直接使用的自然语言片段：

```json
"summary": {
  "phase": "opening",
  "phase_label": "布局阶段",
  "balance": "均衡，白方微领1目",
  "last_move_verdict": "unknown（实战手未被充分搜索）",
  "best_move_note": "D16，与左下白棋呼应，人类1d下此概率47%",
  "complexity_note": "局面清晰，复杂度低",
  "human_vs_engine_gap": "引擎强推D16（81%），人类1d偏好分散在D16和D17之间"
}
```

### F3：`evaluate --move`（假设手评估）

```bash
uv run goteacher evaluate --sgf game.sgf --turn 87 --move R10 --profile rank_1d
```

在当前局面追加一手，返回该手的完整评估。解锁 Q3"如果我下这里可以吗"。

### F4：`scan` 真正实现（全局误手扫描）

```bash
uv run goteacher scan --sgf game.sgf --profile rank_1d --max 8
```

用低 visits（150）批量跑全局，按 `score_loss` 和 `whyInteresting` 排序，输出最值得讲解的 N 手。同时聚合全局误手模式，支持"学生反复犯的错误"分析。

### F5：rawVarTimeLeft / humanStWrError 透传

把这两个字段加进 `RootEvaluation` schema，直接从 KataGo 拿，不需要自己估算阶段和复杂度。

---

## 完整技术栈（目标状态）

```
用户提问（自然语言）
        ↓
   [Agent/Skill 层]
        ↓ 解析意图
        ↓
   [goteacher CLI]
   ├── analyze      → KataGo数据 + humanPolicy + 新字段
   ├── board_render → 棋盘ASCII + 方位语义          ← 新增
   ├── evaluate     → 假设手评估                    ← 新增
   ├── scan         → 全局误手扫描 + 模式聚合        ← 待实现
   └── position_summary → 结构化语义摘要             ← 新增
        ↓
   [LLM 教学层]
   ├── 输入：棋盘图 + 语义摘要 + 学生问题
   ├── 知识：围棋概念（模型自带）
   ├── 检索：相似局面/定式（基于 symHash，未来）
   └── 输出：针对该棋力的自然语言教学
```

---

## 优先级排序

| 优先级 | 工作 | 解锁场景 |
|--------|------|---------|
| P0 | 修复实战手评估缺失 + severity=unknown | 数据可信 |
| P0 | `board_render` 棋盘 ASCII 可视化 | LLM 局面感知，所有问题质量提升 |
| P1 | 透传 `rawVarTimeLeft`、`humanStWrError`、`humanPolicy` | 阶段判断、复杂度、全盘人类偏好 |
| P1 | profile 名称映射 + 错误提示 | 用户体验 |
| P1 | 修复 asyncio 缓冲限制 | 稳定性 |
| P1 | `position_summary` 语义摘要字段 | LLM prompt 质量 |
| P2 | `evaluate` 假设手命令 | Q3 完全解锁 |
| P2 | `scan` 真正实现 | Q5 + 全局分析 |
| P3 | 基于 `symHash` 的定式/相似局面 RAG | 最接近真人教师，工程量大 |

---

## 已知限制

- `includeMovesOwnership`（每个候选手的 ownership 数组）会导致响应超 64KB，需修复缓冲后才能启用
- Human SL 模型（`b18c384nbt-humanv0`）在极端局面（大胜/大败）下 winrate 和 score 估计可能偏差大，教学时注意
- `scan` 批量分析时 KataGo 进程需要保持长连接，当前每次 `analyze` 都重新启动进程，批量场景需要复用连接
- `rawVarTimeLeft` 无固定单位，只能做相对比较，建议按 `>30=布局, 5-30=中盘, <5=官子` 分档