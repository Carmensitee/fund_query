# Changelog

## v2.0.0 — 2026-05-27

### 新增
- **手机端 Streamlit 版**（`streamlit_app.py`）
  - 部署到 Streamlit Cloud，电脑不开机也能在手机上查看
  - 密码锁保护
  - 38 只 QDII LOF 基金默认列表
  - 状态筛选（全部/暂停/限大额/开放）
  - 统计卡片（暂停/限大额/开放/合计）
  - 查询逻辑与桌面版 `fund_server.py` 完全一致
  - 数据变化检测：刷新后自动对比新旧数据，显示具体变动

### 文件
- `streamlit_app.py` — 手机端页面
- `requirements.txt` — Streamlit Cloud 依赖

## v1.2.0 — 2026-05-10

### 变更
- 引入 `logging` 模块替代原始 `print()` 做运行日志
  - 双通道输出：控制台 INFO 级别 + 文件 DEBUG 级别
  - 日志文件：`fund_query/fund_query.log`
  - 统一格式：`时间 [级别] 消息`
- `fetch()` 网络请求异常现在记录到日志（之前静默返回 None）
- 缓存文件读写异常现在记录到日志（之前静默忽略）
- HTTP 请求日志改由 `logger.info` 输出，带时间戳
- 批量查询进度改用 `logger.info`，不再使用 `\r` 覆盖行

### 文件
- `fund_query/fund_server.py`
- `fund_query/fund_limit_query.py`

## v1.1.0 — 2026-05-09

### 新增
- 工具栏增加「状态筛选」下拉框，支持 4 种筛选模式：
  - 全部状态（默认）
  - 仅暂停申购
  - 仅限购（限制大额申购）
  - 仅不限购（开放申购）
- 工具栏增加「排序」下拉框，支持 3 种排序模式：
  - 默认排序
  - 按限购状态排序（限购 > 暂停 > 开放）
  - 按限购金额排序，分4组：有限额（从小到大）→ 需查看公告 → 不限购 → 暂停申购（最后）
- 新增 `getAmountValue(amount)` 函数，将限购金额字符串解析为可排序数值
- 新增 `getGroup(result)` 函数，将基金按限购状态分为4组用于排序

### 变更
- 新增 `getFilteredData(results)` 函数，合并筛选与排序逻辑，二者可组合使用
- `render()` 改为先经 `getFilteredData()` 过滤再渲染，统计卡片数字同步反映筛选结果
- 将 `is_suspended` 与 `is_limited` 分离：
  - 「暂停申购」不再被归类为 `is_limited`
  - 后端 `query_single` / `query_fund` 返回独立字段 `is_suspended`、`is_limited`
  - 前端限购金额列颜色区分：暂停=红色、限购=黄色、正常=绿色
  - CLI 输出标签改为 `X 暂停` / `X 限购` / `O 正常`，底部统计分开计数

### 移除
- 删除「仅未知」状态筛选选项（未知状态实际很少出现，无实用价值）

### 文件
- `fund_query/fund_server.py`
- `fund_query/fund_limit_query.py`
