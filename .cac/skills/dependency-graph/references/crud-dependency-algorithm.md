---
name: dependency-graph
description: 基于"用例 × 实体"CRUD 矩阵，推导用例之间的数据依赖关系（R/U/D 都依赖 C），并在每条边上标注依赖来源（源操作→目标操作，如 R→C、U→C、D→C），输出有向 Graphviz DOT 图，以及依赖边和四元组清单（Markdown）。
---

# 基于 CRUD 矩阵的依赖图构建 (Dependency Graph)

## 作用

当用户已有一个"用例 × 实体"的 CRUD 矩阵，需要推导用例之间的**数据依赖关系**（有向边 `Ux → Uy` 表示 **Ux 依赖 Uy**）时，使用本 skill。

本 skill 输出四份结果：

1. **依赖边清单**（每条边带来源标注 `源操作→目标操作`）
2. **Graphviz 依赖图**（DOT 文本）
3. **机器可读依赖图**（JSON，包含边、标签、实体及逐条来源）
4. **依赖关系四元组清单**（一份 Markdown，把每条依赖关系写成 `源用例，数据依赖于，目标用例，依赖缘由：…`）

---

## 核心公理

```
if U1 reads(a) AND U2 creates(a) then U1 → U2
if U1 updates(a) AND U2 creates(a) then U1 → U2
if U1 deletes(a) AND U2 creates(a) then U1 → U2
```

通俗解释：**读、改、删都依赖创建。** 创建（C）是实体存在的唯一前提，永远是被依赖方。

---

## 定义

1. **实体集合**：\(A=\{a_1,a_2,\dots\}\)
2. **用例集合**：\(U=\{U_1,U_2,\dots\}\)
3. CRUD 枚举：`C`(新建)、`R`(读取)、`U`(更新)、`D`(删除)
   - `C` 是实体存在的**前提**（创建者）
   - `R`、`U`、`D` 都只能作用于已创建的实体，因此 **R、U、D 都依赖 C**

---

## 依赖判定规则

按被依赖操作（U2）划分，源操作（U1）对它的依赖关系如下：

| U1 操作 | U1 依赖的 U2 操作 |
| --- | --- |
| `R`（读） | `C` |
| `U`（更新） | `C` |
| `D`（删除） | `C` |
| `C`（新建） | （无，创建永远是被依赖方，不依赖任何操作） |

> 即：对任意实体 a，任意一对不同用例 \(U_1 \neq U_2\)：
> - 若 \(U_1\) 在 a 上 ∈ {`R`,`U`,`D`} 且 \(U_2\) 在 a 上 = `C` → 边 \(U_1 \rightarrow U_2\)

---

## 边的来源标注（Edge Label）

每条依赖边都必须标注**依赖来源**，即「谁因为什么操作、依赖谁因为什么操作」。格式：

```
U1 ──[源操作→目标操作]──> U2
```

- **源操作** = U1 在实体 a 上的操作（`R` / `U` / `D`）
- **目标操作** = U2 在实体 a 上的操作（恒为 `C`）

由判定规则，只可能产生 3 种标注：

| 标注 | 含义 | 语义类型 |
| --- | --- | --- |
| `R→C` | 读依赖创建 | 生命周期依赖（先创建才能读） |
| `U→C` | 改依赖创建 | 生命周期依赖（先创建才能改） |
| `D→C` | 删依赖创建 | 生命周期依赖（先创建才能删） |

示例：

```
UC01 ──[R→C]──> UC11     UC01 读 Product，UC11 创建 Product
UC04 ──[U→C]──> UC13     UC04 更新 SKU，UC13 创建 SKU
```

### 多来源合并规则

同一对 `U1→U2` 可能命中多条规则（同一实体多种操作，或跨多个实体）。此时：

1. **只保留一条边**（同一 `U1→U2` 去重）。
2. 将该边所有命中的「源操作→目标操作」标注**合并去重**，按固定顺序 `R→C, U→C, D→C` 排序，用逗号连接，如 `[R→C,U→C]`。
3. 同时记录每条边命中的**实体来源**，用于溯源。

---

## 依赖关系四元组（Markdown 清单）

除依赖图外，还需输出一份 Markdown 文档，把**所有依赖关系**逐条列出。每条依赖关系按如下四元组格式：

```
{源用例名}，数据依赖于，{目标用例名}，依赖缘由：{源操作}（{实体}）依赖于{目标操作}（{实体}）
```

- `{源用例名}`：发起依赖的用例（在实体上做 R/U/D 的一方）
- `{目标用例名}`：被依赖的用例（在实体上做 C 的创建者）
- `{源操作}`：源用例在实体上的操作（`R` / `U` / `D`）
- `{目标操作}`：恒为 `C`
- `{实体}`：依赖发生的实体（源、目标两侧为同一实体）

示例：

```
读取订单，数据依赖于，创建订单，依赖缘由：R（订单）依赖于C（订单）
```

> 一条四元组对应**一个依赖缘由**。若同一对用例命中多个缘由（多个实体或多个操作），则拆成多条四元组分别列出，不要合并。

---

## 重要约束

1. 只处理**同一实体 a**上的操作配对；跨实体不产生依赖。
2. \(U_1\) 与 \(U_2\) 必须是两个不同用例，禁止自环（\(U_x \rightarrow U_x\) 过滤掉）。
3. 同一对 `U1→U2` 去重，只保留一条边，但需**合并该对命中的所有标注**（见「多来源合并规则」）。
4. 这是**数据依赖**，不是时序调用依赖。
5. 箭头方向 `U1 -> U2` 表示 **U1 依赖 U2**，不可写反。

---

## 提示词模板（Prompt）

> 执行时，把 `${...}` 占位符替换为实际内容，再将整段 prompt 交给模型。
> 该规则是确定性的，也可按下方"判定规则"直接手工/脚本推导。

You are responsible for deriving use case dependencies from a CRUD matrix.

Input:
(a) CRUD Matrix (use cases × entities, each cell is a subset of {C, R, U, D}):
${crudMatrix}

Task:
Derive all directed dependency edges between use cases, label each edge with its dependency source, and also produce a four-tuple dependency list in Markdown.

Definitions:
- C = Create, R = Read, U = Update, D = Delete.

Dependency Rule:
For the same entity a, for every pair of distinct use cases U1 != U2:
- if U1 in {R, U, D} on a AND U2 = C on a -> add edge U1 -> U2, labeled "<op1>->C" where op1 = U1's op on a.

In words:
- Read (R), Update (U), and Delete (D) all depend only on Create (C).
- Create (C) depends on nothing (it is always the dependency target).

Edge Labels:
Each edge MUST carry a label "source-op -> C". The three possible labels are R->C, U->C, D->C.

Label Aggregation:
- Deduplicate by (U1 -> U2) pair: keep ONE edge per pair.
- If a pair is hit by multiple rules (multiple entities or multiple ops), merge all its labels (dedupe) in the fixed order R->C, U->C, D->C, joined by comma, e.g. "R->C,U->C".
- Record the entities that caused each edge for traceability.

Four-tuple List (Markdown):
For every distinct dependency reason (source use case, target use case, entity, source operation), output one line in this format:
{source use case}，数据依赖于，{target use case}，依赖缘由：{source op}（{entity}）依赖于C（{entity}）

Constraints:
1. Only pair operations on the same entity; no cross-entity dependencies.
2. U1 and U2 must be different use cases; filter out self-loops.
3. One edge per (U1 -> U2) pair, with merged labels.
4. This is a data dependency, not a temporal call dependency.

Output Requirements:
1. First list all derived dependency edges (one per line), each in the form:
   U1 --[label]--> U2   (label = merged source-op->C list), and include the entity/entities that caused the edge.
2. Output a clean Graphviz DOT digraph (digraph G { ... }):
   - node identifiers as the use case IDs;
   - node shape box;
   - one directed edge per pair with its label: U1 -> U2 [label="..."] (arrow direction MUST mean U1 depends on U2);
   - no extra layout, no legend, no comments.
3. Output the four-tuple Markdown list: one line per distinct dependency reason, in the format above.
4. If there are no edges, still output a valid empty digraph (not an empty string).

---

## 输出要求

1. **依赖边清单**：逐条列出 `U1 ──[标注]──> U2`，并附每条边命中的**实体来源**。
2. **Graphviz 依赖图**：一个干净的 DOT digraph 代码块，每条边带 `[label="标注"]`，可直接复制到 Graphviz 渲染器运行。
3. **依赖关系四元组清单**：一份 Markdown，逐条列出 `源用例，数据依赖于，目标用例，依赖缘由：…`。

---

## 不应做的事

- 把箭头方向写反（`U1 -> U2` 代表 U1 依赖 U2）
- 让 C（创建）作为依赖方指向别人（创建永远是被依赖方）
- 让 R、U、D 依赖除 C 之外的操作（R/U/D 只依赖 C，不得出现 R→U、R→D）
- 漏掉边上的来源标注（每条边都必须带 `源操作→C`）
- 同一对 `U1→U2` 出现多条重复边（应合并标注为一条）
- 四元组清单合并多个缘由（一条四元组只对应一个缘由）
- 跨实体配对产生依赖
- 保留自环
- 生成空字符串（无依赖边时也要输出合法空 digraph）
