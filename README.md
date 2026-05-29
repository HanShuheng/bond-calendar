# 可转债提醒助手

这个项目会从集思录可转债日历接口获取事件，筛选可转债申购和上市日期，并生成可被系统日历、Google Calendar、Apple Calendar 等订阅的 `kzz.ics` 文件。不包含 A 股新股申购提醒。

第一版只生成日历订阅文件，不包含邮件、短信、微信、Telegram 等推送功能，也不需要任何密钥。

## 提醒范围

默认保留这些事件：

- 申购日
- 上市日

提醒规则：

- 申购日当天 10:00 提醒一次。
- 申购日当天 12:30 提醒一次。
- 上市日提前 1 天提醒一次。
- 上市日开盘前 30 分钟提醒一次，即当天 09:00。
- 日历事件本身只占用 09:30 到 09:35，用作提醒载体。

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
- 每天 UTC 23:00 自动运行，对应北京时间每天 07:00。
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

数据来源为集思录可转债日历接口：

```text
https://www.jisilu.cn/data/calendar/get_calendar_data/?qtype=CNV
```

该数据来自第三方接口，可能出现延迟、缺失、变更或不可用。本项目仅供学习研究和个人日历提醒使用，不保证投资信息准确性，不构成任何投资建议、交易建议或收益承诺。实际投资操作请以交易所公告、发行人公告和券商系统为准。

使用者应自行判断数据准确性并承担使用风险。因使用或依赖本项目及其生成内容而产生的任何直接或间接损失、争议或法律责任，项目作者不承担责任。

## 失败保护

如果接口请求失败、返回结构异常或 JSON 解析失败，程序会输出 warning 并退出，且不会覆盖已有的 `kzz.ics`。
