# 可转债提醒助手

这个项目会从东方财富可转债接口获取事件，生成可转债申购、中签公布和上市日期提醒，并生成可被系统日历、Google Calendar、Apple Calendar 等订阅的 `kzz.ics` 文件。不包含 A 股新股申购提醒。集思录可转债日历接口仅作为兜底数据源。

第一版只生成日历订阅文件，不包含邮件、短信、微信、Telegram 等推送功能，也不需要任何密钥。

## 提醒范围

默认保留这些事件：

- 申购日
- 中签公布
- 上市日

提醒规则：

- 申购日当天 10:00 提醒一次。
- 申购日当天 12:30 提醒一次。
- 中签公布当天 10:30 提醒一次。
- 中签公布当天 13:00 提醒一次。
- 上市日提前 1 天提醒一次。
- 上市日开盘前 5 分钟提醒一次，即当天 09:25。
- 上市日当天 11:00 提醒一次。
- 上市日下午 13:30 提醒一次。
- 日历事件本身只占用 09:30 到 09:35，用作提醒载体。

`中签公布` 使用东方财富字段 `BOND_START_DATE`。该字段在页面上叫“中签号发布日”，提醒含义是“查看中签结果；如中签则按券商要求缴款”，不代表一定中签。

如果可转债上市首日涨幅达到 30%，通常会临时停牌至 14:57 附近。是否达到 30% 需要在交易日当天 14:50 左右查询实时行情后判断；订阅日历不会保证分钟级刷新，因此本项目的 ICS 文件不动态生成“14:55 条件提醒”。这类提醒更适合另做盘中监控和即时推送。

事件时间按北京时间 `Asia/Shanghai` 生成。

## 本地运行

在项目目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
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

## 日历订阅

推荐使用 GitHub Pages 地址订阅：

```text
https://hanshuheng.github.io/bond-calendar/kzz.ics
```

如果日历软件不接受 `https://`，可以改用 `webcal://`：

```text
webcal://hanshuheng.github.io/bond-calendar/kzz.ics
```

请使用“订阅日历”，不要反复下载并导入 `.ics` 文件。订阅会随着远端 `kzz.ics` 自动更新；导入只是静态复制，后续不会自动同步，也更容易产生重复事件。

`raw.githubusercontent.com` 在部分网络环境下可能超时，不作为首选订阅地址。

## GitHub Actions 自动更新

`.github/workflows/update-ics.yml` 已配置：

- 支持手动触发 `workflow_dispatch`。
- 每天 UTC 23:00、01:00、03:00 自动运行，对应北京时间每天 07:00、09:00、11:00；多跑几次可以降低 GitHub 定时任务延迟或漏跑的影响。
- 运行 `python -m unittest discover -s tests` 检查筛选、提醒和 UID 规则。
- 运行 `python main.py` 生成 `kzz.ics`。
- 只在 `kzz.ics` 有变化时提交。
- 提交时只执行 `git add kzz.ics`。

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

## 数据来源与风险说明

当前程序主要使用东方财富可转债申购页面及接口：

```text
https://data.eastmoney.com/xg/xg/?mkt=kzz
https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_BOND_CB_LIST&columns=ALL&source=WEB&client=WEB
```

如果东方财富接口请求失败、返回结构异常或没有可用事件，程序会使用集思录可转债日历接口作为兜底：

```text
https://www.jisilu.cn/data/calendar/get_calendar_data/?qtype=CNV
```

东方财富接口字段说明见 [docs/eastmoney-bond-fields.md](docs/eastmoney-bond-fields.md)。

上述数据均来自第三方接口，可能出现延迟、缺失、错误、变更或不可用。本项目仅供学习、研究和技术交流使用，学习完成后请自行删除本项目及其生成文件。本项目不构成投资建议、交易建议、数据服务或任何形式的收益承诺，不保证任何数据或提醒的准确性、完整性、及时性和可用性。

使用者应自行核验数据准确性并自行承担使用风险。因使用、传播、修改、部署或依赖本项目及其生成内容而产生的任何直接或间接损失、争议或法律责任，均与项目开发者无关，项目开发者不承担任何责任。实际投资操作请以交易所公告、发行人公告、券商系统和官方披露信息为准。

## 失败保护

如果东方财富接口请求失败、返回结构异常或没有可用事件，程序会输出 warning 并尝试使用集思录接口兜底。只有两个数据源都不可用时，程序才会退出并保留已有的 `kzz.ics`，避免用空文件覆盖订阅日历。
