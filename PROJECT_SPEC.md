# 公开汇总数据发布约束检查：生产工作流

审核和发布使用完整 `examples/region.json`，可加 `node_budget`（1–5000，默认 300）。`public` 固定为其公开值，`zero` 必须为公开的结构零；`masked` 取从 0 到 `max_count` 的整数。关系公开且由互异分项之和构成。每个遮蔽项只要求至少一个不同值的全表可行分配；就单表和给定模型作判定，并不保证匿名性。审核接口是本地受信任入口，不把原始计数存入数据库。输入最多 60 个单元格与 60 个关系，项目不接个人级数据。

| API | 正常结果 | 异常结果 |
| --- | --- | --- |
| `POST /release/reviews` | 对单表的已公开整数约束判断每个遮蔽项是否存在不同值的可行分配。 | 关系失衡返回 400；结论唯一或预算耗尽则给出 hold。 |
| `POST /release/publications` | 对请求重新审核，仅保存去掉遮蔽计数和内部诊断的公开清单。 | 审核未放行则返回 400，不写入新制品。 |
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
