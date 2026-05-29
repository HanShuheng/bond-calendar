# 可转债提醒助手

这个项目会从集思录可转债日历接口获取事件，筛选常见可转债关键日期，并生成可被系统日历、Google Calendar、Apple Calendar 等订阅的 `kzz.ics` 文件。

第一版只生成日历订阅文件，不包含邮件、短信、微信、Telegram 等推送功能，也不需要任何密钥。

## 提醒范围

默认保留这些事件：

- 申购日
- 上市日
- 最后交易日
- 最后转股日
- 强赎
- 下修股东会

提醒规则：

- 所有事件提前 1 天提醒一次。
- 所有事件开盘前 30 分钟提醒一次。
- 申购日额外在当天 11:00 左右提醒一次。

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

## 日历订阅

如果把项目发布到 GitHub，并启用 GitHub Actions 自动更新，可以使用 Raw 文件地址订阅：

```text
https://raw.githubusercontent.com/<owner>/<repo>/main/kzz.ics
```

把 `<owner>` 和 `<repo>` 替换成你的 GitHub 用户名和仓库名。若默认分支不是 `main`，请替换为实际分支名。

## GitHub Actions 自动更新

`.github/workflows/update-ics.yml` 已配置：

- 支持手动触发 `workflow_dispatch`。
- 每天 UTC 23:00 自动运行，对应北京时间每天 07:00。
- 运行 `python main.py` 生成 `kzz.ics`。
- 只在 `kzz.ics` 有变化时提交。
- 提交时只执行 `git add kzz.ics`。

## 数据来源与风险说明

数据来源为集思录可转债日历接口：

```text
https://www.jisilu.cn/data/calendar/get_calendar_data/?qtype=CNV
```

该数据来自第三方接口，可能出现延迟、缺失、变更或不可用。本项目仅用于个人日历提醒，不保证投资信息准确性，不构成任何投资建议。实际投资操作请以交易所公告、发行人公告和券商系统为准。

## 失败保护

如果接口请求失败、返回结构异常或 JSON 解析失败，程序会输出 warning 并退出，且不会覆盖已有的 `kzz.ics`。
