# 可转债提醒助手

这个项目会自动生成可订阅的可转债提醒日历 `kzz.ics`。项目核心只认统一的标准事件数据，具体数据来源由用户通过适配器提供；仓库内置东方财富和集思录作为可运行示例。

项目只生成日历订阅文件，不包含邮件、短信、微信、Telegram 等推送功能，也不需要任何密钥。不包含 A 股新股申购提醒。

## 功能概览

- 使用“策略模式 + 适配器模式”：配置决定数据源策略，适配器负责把原始数据转换为标准事件。
- 内置东方财富、集思录两个示例适配器，用户也可以接入自己的数据源。
- 生成标准 `ICS` 日历文件。
- 支持系统日历、Google Calendar、Apple Calendar 等订阅。
- 使用稳定 UID，避免同一事件在日历中重复添加。
- GitHub Actions 每天自动更新，并可同步到 Gitee。
- 默认策略顺序为 `eastmoney,jisilu`；前一个策略没有可用事件时，会继续尝试下一个策略。

## 提醒规则

默认保留 3 类事件：

- 申购日
- 中签公布
- 上市日

| 事件 | 标准事件类型 | 提醒时间 | 说明 |
|---|---|---|---|
| 申购日 | `subscribe` | 当天 10:00、12:30 | 提醒今天可以申购 |
| 中签公布 | `ballot` | 当天 10:30、13:00 | 提醒查看中签结果；如中签再按券商要求处理 |
| 上市日 | `list` | 前一天、当天 09:25、当天 11:00、当天 13:30 | 提醒上市交易窗口 |

所有事件本身只占用当天 `09:30-09:35`，只是作为提醒载体。事件时间按北京时间 `Asia/Shanghai` 生成。

在内置东方财富示例适配器中，`PUBLIC_START_DATE` 会转换为 `subscribe`，`BOND_START_DATE` 会转换为 `ballot`，`LISTING_DATE` 会转换为 `list`。其中 `BOND_START_DATE` 在页面上叫“中签号发布日”，本项目统一显示为“中签公布”，含义是“查看中签结果；如中签则按券商要求缴款”，不代表一定中签。

如果可转债上市首日涨幅达到 30%，通常会临时停牌至 14:57 附近。是否达到 30% 需要在交易日当天 14:50 左右查询实时行情后判断；订阅日历不会保证分钟级刷新，因此本项目的 ICS 文件不动态生成“14:55 条件提醒”。这类提醒更适合另做盘中监控和即时推送。

## 事件关系

同一只可转债通常会按下面的业务顺序出现：

```text
申购日 -> 中签公布 -> 上市日
```

在 ICS 中它们是独立事件，依靠相同的转债代码和名称关联。例如：

```text
123271-subscribe-2026-06-02@bond-calendar
123271-payment-2026-06-04@bond-calendar
123271-list-2026-xx-xx@bond-calendar
```

这样可以让每个日期单独更新、单独提醒，并保持 UID 稳定。

## ICS 描述模板

日历事件描述会尽量压缩成短字段，避免手机日历详情过长：

```text
【申购日】通合转债
代码: 123271
申购: 370491
正股: 通合科技(300491)
登记: 2026-06-01 | 配售: 2.9377/股
规模: 5.22亿 | 评级: AA
来源: 东方财富
详情: https://data.eastmoney.com/kzz/detail/123271.html
```

## 本地运行

在项目目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --config config/default.toml --output kzz.ics
```

成功后会生成或更新：

```text
kzz.ics
```

可用下面的命令快速查看结果：

```bash
grep -n "BEGIN:VCALENDAR\\|BEGIN:VEVENT\\|SUMMARY" kzz.ics | head -40
```

本地规则测试：

```bash
python -m unittest discover -s tests
```

无参数运行仍然可用：

```bash
python main.py
```

它等价于使用默认配置 `config/default.toml` 并输出到 `kzz.ics`。

## 配置文件

默认配置文件是：

```text
config/default.toml
```

主要配置项：

| 配置 | 说明 |
|---|---|
| `calendar.output_file` | 默认输出文件 |
| `calendar.timezone` | 事件时区，默认 `Asia/Shanghai` |
| `calendar.event_lookback_days` | 保留今天前多少天以来的事件 |
| `calendar.sources` | 数据源顺序，默认 `["eastmoney", "jisilu"]` |
| `events.*.alarms` | 各事件类型的提醒规则 |
| `adapters.*` | 数据源适配器的类路径、接口、超时、重试等配置 |

CLI 和环境变量可覆盖部分配置：

```bash
python main.py --config config/default.toml --output kzz.ics --source eastmoney
```

支持的环境变量见 [.env.example](.env.example)：

```text
BOND_CALENDAR_CONFIG=config/default.toml
BOND_CALENDAR_OUTPUT=kzz.ics
BOND_CALENDAR_SOURCE=eastmoney,jisilu
```

`.env` 只用于本地覆盖，不要提交到 Git。

## 数据源适配器

项目核心逻辑只依赖标准事件对象，不直接依赖东方财富、集思录或任何第三方字段。这里的设计分成两层：

- 数据层：每个适配器负责请求、读取、清洗自己的原始数据。
- 业务层：只接收 `BondEvent` 标准事件，负责提醒规则、稳定 UID 和 ICS 生成。

本项目采用“策略模式 + 适配器模式”：

- 策略模式：`calendar.sources` 决定数据源尝试顺序，例如 `["eastmoney", "jisilu"]`。
- 适配器模式：每个数据源把自己的原始字段转换成统一的 `BondEvent`。

内置适配器只是示例：

- `eastmoney`：读取东方财富 `RPT_BOND_CB_LIST`，可生成 `subscribe`、`ballot`、`list`。
- `jisilu`：读取集思录可转债日历，可生成其接口中已有的标准事件。

适配器需要输出统一字段：

| 字段 | 说明 |
|---|---|
| `code` | 转债代码，必填 |
| `name` | 转债简称，必填 |
| `event_type` | `subscribe`、`ballot`、`list` 之一 |
| `event_date` | 事件日期 |
| `detail_url` | 详情页，可选 |
| `description_fields` | 日历描述短字段，可选 |
| `source` | 数据源名称，可选 |

新增自定义数据源时，实现一个 Python 适配器，把你的原始数据转换成上述标准事件即可。配置中可以通过 `adapters.<name>.class` 指向你的适配器类，无需修改 ICS 生成逻辑。详细说明见 [docs/adapter-guide.md](docs/adapter-guide.md)。

## 输出文件

项目核心输出是仓库根目录下的：

```text
kzz.ics
```

它是最终用于订阅的日历文件。请使用“订阅日历”，不要反复下载并导入 `.ics` 文件；导入只是静态复制，后续不会自动同步，也更容易产生重复事件。

## 日历订阅

推荐使用 GitHub Pages 地址订阅：

```text
https://hanshuheng.github.io/bond-calendar/kzz.ics
```

如果日历软件不接受 `https://`，可以改用 `webcal://`：

```text
webcal://hanshuheng.github.io/bond-calendar/kzz.ics
```

如果所在网络访问 GitHub 不稳定，也可以使用 Gitee raw 地址：

```text
https://gitee.com/shuheng17/bond-calendar/raw/main/kzz.ics
```

`raw.githubusercontent.com` 在部分网络环境下可能超时，不作为首选订阅地址。

## GitHub Actions 自动更新

`.github/workflows/update-ics.yml` 已配置：

- 支持手动触发 `workflow_dispatch`。
- 每天 UTC 23:00、01:00、03:00 自动运行，对应北京时间每天 07:00、09:00、11:00；多跑几次可以降低 GitHub 定时任务延迟或漏跑的影响。
- 运行 `python -m unittest discover -s tests` 检查筛选、提醒和 UID 规则。
- 运行 `python main.py` 生成 `kzz.ics`。
- 只在 `kzz.ics` 有变化时提交。
- 提交时只执行 `git add kzz.ics`。
- 如已配置 Gitee secrets，会自动同步到 Gitee。

仓库已启用 GitHub Pages，从 `main` 分支根目录发布，因此 `kzz.ics` 更新后会通过 Pages 地址提供订阅。

## 同步到 Gitee

如果所在网络访问 GitHub 或 GitHub Pages 不稳定，可以把仓库同步到 Gitee，再使用 Gitee raw 地址订阅：

```text
https://gitee.com/<你的Gitee用户名>/bond-calendar/raw/main/kzz.ics
```

推荐方式是继续让 GitHub Actions 负责每天生成 `kzz.ics`，然后自动推送一份到 Gitee。配置步骤：

1. 在 Gitee 新建一个空仓库，例如 `bond-calendar`。不要初始化 README，避免第一次推送出现非快进冲突。
2. 在 Gitee 生成私人令牌，至少需要仓库读写权限。
3. 到 GitHub 仓库的 `Settings -> Secrets and variables -> Actions` 添加 3 个 Repository secrets：

```text
GITEE_USERNAME  你的 Gitee 用户名
GITEE_TOKEN     你的 Gitee 私人令牌
GITEE_REPO      bond-calendar
```

配置完成后，GitHub Actions 每次运行都会在更新 GitHub 后同步到 Gitee。若这 3 个 secrets 没有配置，Gitee 同步步骤会自动跳过，不影响 GitHub 更新。

## 项目结构

```text
.
├── main.py                          # CLI 入口
├── bond_calendar/                   # 核心包
├── config/default.toml              # 默认配置
├── kzz.ics                          # 日历订阅文件
├── requirements.txt                 # Python 依赖
├── tests/test_calendar_rules.py     # 规则测试
├── docs/adapter-guide.md            # 适配器开发说明
├── docs/eastmoney-bond-fields.md    # 东方财富示例字段说明
└── .github/workflows/update-ics.yml  # 自动更新工作流
```

## 数据来源与风险说明

本项目的数据来源由适配器决定。默认配置提供两个内置示例策略，方便直接运行：

| 策略名 | 示例数据来源 | 说明 |
|---|---|---|
| `eastmoney` | `https://data.eastmoney.com/xg/xg/?mkt=kzz` | 读取东方财富 `RPT_BOND_CB_LIST` 接口 |
| `jisilu` | `https://www.jisilu.cn/data/calendar/get_calendar_data/?qtype=CNV` | 读取集思录可转债日历接口 |

东方财富示例适配器字段说明见 [docs/eastmoney-bond-fields.md](docs/eastmoney-bond-fields.md)。自定义数据源只要输出标准事件对象即可，不需要使用上述两个网站。

上述数据均来自第三方接口，可能出现延迟、缺失、错误、变更或不可用。本项目仅供学习、研究和技术交流使用，学习完成后请自行删除本项目及其生成文件。本项目不构成投资建议、交易建议、数据服务或任何形式的收益承诺，不保证任何数据或提醒的准确性、完整性、及时性和可用性。

使用者应自行核验数据准确性并自行承担使用风险。因使用、传播、修改、部署或依赖本项目及其生成内容而产生的任何直接或间接损失、争议或法律责任，均与项目开发者无关，项目开发者不承担任何责任。实际投资操作请以交易所公告、发行人公告、券商系统和官方披露信息为准。

## 失败保护

程序会按 `calendar.sources` 配置的策略顺序依次尝试数据源。某个策略请求失败、返回结构异常或没有可用事件时，程序会输出 warning 并尝试下一个策略。所有策略都不可用时，程序会退出并保留已有的 `kzz.ics`，避免用空文件覆盖订阅日历。
