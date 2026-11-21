# 公开汇总数据发布约束检查：生产工作流

审核和发布使用完整 `examples/region.json`，可加 `node_budget`（1–5000，默认 300）。`public` 固定为其公开值，`zero` 必须为公开的结构零；`masked` 取从 0 到 `max_count` 的整数。关系公开且由互异分项之和构成。

未提供 `min_candidates` 时保持旧语义：每个遮蔽项只要求至少一个不同值的全表可行分配；就单表和给定模型作判定，并不保证匿名性。

请求可加可选的 `min_candidates` 对象，把遮蔽项映射到该格至少需要的互异整数候选数（含观测值，1–257；2 等价于旧语义）。指定项逐值枚举可行整数并计数，整数孔洞不会被最大值减最小值掩盖；计数达到下限即放行，枚举完毕仍不足则判 `insufficient_candidates`。未指定的遮蔽项仍按旧语义判断。审核接口是本地受信任入口，不把原始计数存入数据库。输入最多 60 个单元格与 60 个关系，项目不接个人级数据。

| API | 正常结果 | 异常结果 |
| --- | --- | --- |
| `POST /release/reviews` | 对单表的已公开整数约束判断每个遮蔽项是否存在不同值的可行分配；指定 `min_candidates` 的项改判互异候选数是否达标。 | 关系失衡或策略非法返回 400；结论唯一、候选不足或预算耗尽则给出 hold。 |
| `POST /release/publications` | 对请求重新审核，仅保存去掉遮蔽计数和内部诊断的公开清单，并记录所适用的保护口径。 | 审核未放行则返回 400，不写入新制品。 |
| `GET /release/publications/{id}` | 从 SQLite 重读对外清单；仅改变原始遮蔽值不应改变同一公开清单的 ID。 | 未知 ID 返回 404。 |

## 源码边界

- `release/app.py`
- `release/constraints.py`
- `release/model.py`
- `release/publication.py`
- `release/review.py`
- `release/search.py`
- `release/service.py`
- `release/store.py`

HTTP 绑定回环地址，仅供本地开发和合成数据验证。未包含完整测试套件；可运行公开冒烟流程验收当前承诺，不含后续任务测试或参考实现。
