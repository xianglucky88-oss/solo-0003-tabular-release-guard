# 公开汇总数据发布约束检查

离线 Python 数据处理服务，不依赖 pip、外部数据库或网络服务。使用 Python 3.9 或更新版本及标准库中的 SQLite。数据契约见 [PROJECT_SPEC.md](PROJECT_SPEC.md)。

## 验证当前工作流

```sh
python3 -X pycache_prefix=__pycache__ -m compileall -q release examples
python3 -m examples.smoke
```

冒烟流程经真实 WSGI 请求入口执行，使用临时 SQLite 并覆盖正常、拒绝和重新打开数据库后的读取。样例均为合成数据。其中 [`examples/candidates_contiguous.json`](examples/candidates_contiguous.json) 与 [`examples/candidates_sparse.json`](examples/candidates_sparse.json) 的 `c1` 极值范围同为 0–4，但分别有 5 个和 3 个可行整数；同一 `min_candidates` 下前者放行、后者 hold，且稀疏表中存在孔洞。

## 启动服务

```sh
python3 -m release.app --port 8763 --db release-artifacts.sqlite3
```

默认只监听 `127.0.0.1:8763`，`GET /health` 返回状态。试用数据入口：向 `POST /release/reviews` 提交 [`examples/region.json`](examples/region.json) 的 JSON。详见接口表中的输入与存储边界。
