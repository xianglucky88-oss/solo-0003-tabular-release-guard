# 公开汇总数据发布约束检查：生产工作流

审核和发布使用完整 `examples/region.json`，可加 `node_budget`（1–5000，默认 300）。`public` 固定为其公开值，`zero` 必须为公开的结构零；`masked` 取从 0 到 `max_count` 的整数。关系公开且由互异分项之和构成。每个遮蔽项只要求至少一个不同值的全表可行分配；就单表和给定模型作判定，并不保证匿名性。审核接口是本地受信任入口，不把原始计数存入数据库。输入最多 60 个单元格与 60 个关系，项目不接个人级数据。

| API | 正常结果 | 异常结果 |
| --- | --- | --- |
| `POST /release/reviews` | 对单表的已公开整数约束判断每个遮蔽项是否存在不同值的可行分配。 | 关系失衡返回 400；结论唯一或预算耗尽则给出 hold。 |
| `POST /release/cross-reviews` | 以已存储公开清单为参照，合并调用者给出的跨版单元映射后，判断两版全部遮蔽项是否仍有不同值的可行分配。 | 映射无法由公开证据支撑（结构非法、公开余额不符、同名歧义未限定、合并后与公开值矛盾）返回 400 且 `reason=unsupported_mapping`；预算耗尽给出 `indeterminate`；结论唯一给出 hold。 |
| `POST /release/publications` | 对请求重新审核，仅保存去掉遮蔽计数和内部诊断的公开清单；请求附带 `reference` 与 `mapping` 时还须通过跨版审核。 | 审核未放行或跨版审核未通过返回 400，不写入新制品。 |
| `GET /release/publications/{id}` | 从 SQLite 重读对外清单；仅改变原始遮蔽值不应改变同一公开清单的 ID。 | 未知 ID 返回 404。 |

## 跨版审核契约

- 参照侧只能是已发布的公开清单：遮蔽单元在清单中没有计数，解析器拒绝任何给遮蔽项附带计数的清单，历史私有计数无法回流审核。
- 映射由调用者显式提供，包含 `relations`（跨版加和关系）、`only_reference`、`only_candidate`，且必须把两版每个单元归类为“已映射”或“本版独有”。
- 同名不等于同范围：两侧同时存在的名字在映射关系中必须写成 `reference.<id>` 或 `candidate.<id>`，未限定的重名引用直接判为映射不支持。
- 全公开的映射关系必须用公开值通过余额核对；触及遮蔽单元的关系作为调用者断言的联结进入合并约束系统，若与公开事实矛盾使合并系统不可行，仍判为映射不支持，而不是给出风险结论。
- 每个遮蔽单元经二分可行性检查得到取值宽度：`uniquely_determined`（确有推定风险）、`alternative_exists`、`indeterminate`（节点预算不足），三者相互区分。

## 源码边界

- `release/app.py`
- `release/constraints.py`
- `release/crossreview.py`
- `release/model.py`
- `release/publication.py`
- `release/review.py`
- `release/search.py`
- `release/service.py`
- `release/store.py`

HTTP 绑定回环地址，仅供本地开发和合成数据验证。未包含完整测试套件；可运行公开冒烟流程验收当前承诺，不含后续任务测试或参考实现。
