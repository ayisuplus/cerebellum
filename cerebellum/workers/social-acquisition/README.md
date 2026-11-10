# cerebellum-social-acquisition-worker

Isolated discovery worker for Chinese hot boards and academic paper sources.
Claims `social_acquisition_v1` jobs from the Cerebellum control plane, runs the
platform's discovery provider, and submits one immutable
`AcquisitionWorkerResult` per job: a board-level snapshot Document plus the
item URLs (`discovered_urls`) for the control plane to fan out as ordinary
`document_acquire_v1` fetches (handled by `workers/web-acquisition`).

Trust boundary: this worker has job-level output rights only. Storage,
scheduling, cursors, per-document fetching, and escalation all belong to the
control plane; the worker keeps no state between jobs.

## Providers

### Public hot boards (access_mode = public)

| kind       | endpoint                                                        | port source |
|------------|-----------------------------------------------------------------|-------------|
| `weibo`    | `weibo.com/ajax/side/hotSearch`                                 | hottrack    |
| `zhihu`    | `api.zhihu.com/topstory/hot-list` (APP 域名，匿名开放)          | hottrack    |
| `douyin`   | `www.douyin.com/aweme/v1/web/hot/search/list/`                  | hottrack    |
| `bilibili` | `api.bilibili.com/x/web-interface/popular` (wbi 签名主路径)     | 达人站 wbi  |
| `xhs`      | `www.xiaohongshu.com/explore` (SSR `__INITIAL_STATE__` 解析)    | hottrack    |
| `baidu`    | `top.baidu.com/api/board?platform=wise&tab=realtime`            | hottrack    |
| `kuaishou` | `POST www.kuaishou.com/graphql` (`visionHotRank`)               | hottrack    |
| `tieba`    | `tieba.baidu.com/hottopic/browse/topicList`                     | hottrack    |

xhs 的搜索/详情 stub 未移植（只有热榜/推荐页）。

### Paper collectors

| kind       | endpoint                                             |
|------------|------------------------------------------------------|
| `openalex` | `api.openalex.org/works`（令牌桶限流 + 游标分页；`CEREBELLUM_OPENALEX_MAILTO` 进 polite pool） |
| `arxiv`    | `export.arxiv.org/api/query`（每分类串行，3.5s 间隔） |
| `journal`  | Nature / Science 等 5 刊 RSS/RDF                     |

### Authenticated chain (fail-closed)

`douyin` / `xhs` 在 SourcePolicy `access_mode=authenticated_local` 时走
cookie 直采（`auth.py`）。前置条件不满足即按门禁语义 blocked，绝不造假数据：

- policy 非 `authenticated_local` → `policy_denied`
- `CEREBELLUM_{DOUYIN,XHS}_COOKIE_FILE` 未配置 / 文件缺失 / 内容不合格
  （xhs 必须含 `web_session`）→ `auth_required`

cookie 从环境变量指定的本地文件读取，绝不进入日志、错误消息或提交内容。
**本仓库不携带任何明文 cookie 或 API key。**

## Enrichment

`event_cluster.py`（CJK bigram + Jaccard 贪心聚类，移植自 hottrack）对同批次
条目做跨平台事件归并：出现在 ≥2 个平台的相似条目写同一 `cluster_id` 进
Document metadata 扩展字段。单平台批次天然不产生 cluster_id。

## Known limitations (fail-closed by design)

- 抖音/知乎接口的签名与风控策略变化时，匿名请求可能返回 0 条或非 200。
  此时上报 `partial_content`/`rate_limited` 等真实 outcome，不出假数据
  （hottrack 时期即存在的已知现状）。
- bilibili wbi 签名密钥获取失败时退化为匿名裸调，成功率下降但不阻断。

## Configuration

```bash
CEREBELLUM_URL=http://127.0.0.1:7878        # control plane base URL
CEREBELLUM_TOKEN=                           # bearer token
WORKER_ID=social-acquisition-1
CEREBELLUM_DOUYIN_COOKIE_FILE=              # optional
CEREBELLUM_XHS_COOKIE_FILE=                 # optional
CEREBELLUM_OPENALEX_MAILTO=                 # optional
```

## Run

```bash
pip install .
cerebellum-social-acquisition-worker --once   # 单次模式（测试/调试）
python -m cerebellum_social_acquisition       # 常驻轮询
```

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests
```
