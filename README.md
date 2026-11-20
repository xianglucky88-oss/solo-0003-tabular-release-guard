# 公开汇总数据发布约束检查

离线 Python 数据处理服务，不依赖 pip、外部数据库或网络服务。使用 Python 3.9 或更新版本及标准库中的 SQLite。数据契约见 [PROJECT_SPEC.md](PROJECT_SPEC.md)。

## 验证当前工作流

```sh
python3 -X pycache_prefix=__pycache__ -m compileall -q release examples
python3 -m examples.smoke
python3 -m examples.advice
```

冒烟流程经真实 WSGI 请求入口执行，使用临时 SQLite 并覆盖正常、拒绝和重新打开数据库后的读取。样例均为合成数据。

## 遮蔽建议

`POST /release/advice` 与审核接口接受同一张表，再附加：

- `required_public`：必须继续保持公开的现有公开项；
- `maskable`：编辑愿意额外遮蔽的现有公开项；
- `release_values`：各公开项的发布价值（非负整数），用于比较“保住多少价值”；
- 可选 `min_release_value`：必须先满足的发布价值下限；
- 可选 `node_budget`（同审核，1–5000，默认 300）与 `search_budget`（最多尝试多少个组合，1–20000，默认 512）。

建议只做加法：已遮蔽项继续遮蔽，结构零、源计数和关系都不改，也不发布任何制品。每个候选视图都调用与 `POST /release/reviews` 相同的审核函数，因此新遮蔽项也必须至少有另一个可行取值，而不是一遮就被其他关系解出来。

返回 `status` 为 `ok`、`partial`、`incomplete` 或 `unsatisfiable`。同时给出 `minimum_mask`（遮蔽格数最少的方案）与 `best_value`（保留发布价值最高的方案）；两者可能不是同一个方案，`same_result` 会说明。`*_certified` 表示该方案在对应目标上是否已被穷举证实（`recommended_certified` 指在满足发布价值下限的前提下没有更少遮蔽的方案）。不可满足时给出 `unsatisfiable`（含始终被解出的原始遮蔽项与放宽哪个必留项就能成立），搜索未完成时不给推荐，`notes` 用文字说明原因。

`examples/advice.py` 使用交叉边际合成表 [`examples/cross-margins.json`](examples/cross-margins.json)：把建议方案套回原表后提交给现有审核与发布接口，断言审核放行且公开清单不含遮蔽计数。

## 启动服务

```sh
python3 -m release.app --port 8763 --db release-artifacts.sqlite3
```

默认只监听 `127.0.0.1:8763`，`GET /health` 返回状态。试用数据入口：向 `POST /release/reviews` 提交 [`examples/region.json`](examples/region.json) 的 JSON。详见接口表中的输入与存储边界。
