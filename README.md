# 公开汇总数据发布约束检查

离线 Python 数据处理服务，不依赖 pip、外部数据库或网络服务。使用 Python 3.9 或更新版本及标准库中的 SQLite。数据契约见 [PROJECT_SPEC.md](PROJECT_SPEC.md)。

## 验证当前工作流

```sh
python3 -X pycache_prefix=__pycache__ -m compileall -q release examples
python3 -m examples.smoke
python3 -m examples.partial
```

冒烟流程经真实 WSGI 请求入口执行，使用临时 SQLite 并覆盖正常、拒绝和重新打开数据库后的读取。样例均为合成数据。

`examples/partial.py` 用同一张含一个难判区域和一个独立简单区域的表（`examples/mixed.json`），在低预算（4）和充足预算（300）下各跑一次审核：低预算下简单区域的格子先得到结论，难判区域保持 `indeterminate`；同时核对重命名、重排不改变简单结论，且 `nodes_used` 从未超过预算。

## 启动服务

```sh
python3 -m release.app --port 8763 --db release-artifacts.sqlite3
```

默认只监听 `127.0.0.1:8763`，`GET /health` 返回状态。试用数据入口：向 `POST /release/reviews` 提交 [`examples/region.json`](examples/region.json) 的 JSON。详见接口表中的输入与存储边界。
