# 公开汇总数据发布约束检查

离线 Python 数据处理服务，不依赖 pip、外部数据库或网络服务。使用 Python 3.9 或更新版本及标准库中的 SQLite。数据契约见 [PROJECT_SPEC.md](PROJECT_SPEC.md)。

## 验证当前工作流

```sh
python3 -X pycache_prefix=__pycache__ -m compileall -q release examples
python3 -m examples.smoke
python3 -m examples.cross_release
```

冒烟流程经真实 WSGI 请求入口执行，使用临时 SQLite 并覆盖正常、拒绝和重新打开数据库后的读取。跨版演示覆盖：两版各自审核均放行但合并后遮蔽值被唯一推定、预算耗尽的独立结论、同名不同范围的合法分离与强行合并被拒、映射矛盾与私有计数回流拦截。样例均为合成数据。

## 启动服务

```sh
python3 -m release.app --port 8763 --db release-artifacts.sqlite3
```

默认只监听 `127.0.0.1:8763`，`GET /health` 返回状态。试用数据入口：向 `POST /release/reviews` 提交 [`examples/region.json`](examples/region.json) 的 JSON。详见接口表中的输入与存储边界。
