# 数据源适配器开发说明

本项目不要求用户必须使用东方财富或集思录。任何数据源都可以接入，只要把原始数据转换成项目的标准事件对象。

## 分层与设计模式

项目按两层组织：

- 数据层：适配器负责获取和清洗原始数据，可以来自网页接口、数据库、CSV、手工维护的 JSON 或其他服务。
- 业务层：日历生成器只接收标准事件，统一处理标题、提醒、UID、排序和 ICS 输出。

对应的设计模式：

- 策略模式：`calendar.sources` 是数据源策略列表，程序按顺序尝试，先拿到可用标准事件的策略会被用于本次生成。
- 适配器模式：每个适配器把自己的原始字段转换成 `BondEvent`，业务层不关心原始字段叫什么。

东方财富和集思录只是仓库内置示例，不是项目唯一的数据输入方式。

## 标准事件

适配器最终需要输出 `BondEvent`：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `code` | `str` | 是 | 转债代码，用于生成稳定 UID |
| `name` | `str` | 是 | 转债简称，用于生成标题 |
| `event_type` | `str` | 是 | `subscribe`、`ballot`、`list` 之一 |
| `event_date` | `date` | 是 | 事件日期 |
| `detail_url` | `str` | 否 | 详情页链接 |
| `description_fields` | `tuple[str, ...]` | 否 | 写入日历描述的短字段 |
| `source` | `str` | 否 | 数据源名称 |

事件类型映射：

| `event_type` | 日历标题 |
|---|---|
| `subscribe` | `【申购日】xxx转债` |
| `ballot` | `【中签结果公布】xxx转债` |
| `list` | `【上市日】xxx转债` |

## 适配器接口

适配器类需要实现 `fetch` 方法：

```python
from datetime import date

from bond_calendar.models import AdapterResult, BondEvent, CalendarConfig


class MyAdapter:
    name = "我的数据源"

    def fetch(self, config: CalendarConfig, today: date | None = None) -> AdapterResult | None:
        events = (
            BondEvent(
                code="123456",
                name="示例转债",
                event_type="subscribe",
                event_date=date(2026, 6, 1),
                detail_url="https://example.com/bond/123456",
                description_fields=("申购: 370000", "来源: 我的数据源"),
                source=self.name,
            ),
        )
        return AdapterResult(source=self.name, raw_count=1, events=events)
```

推荐在配置中声明适配器类路径：

```toml
[calendar]
sources = ["my_source"]

[adapters.my_source]
class = "my_package.my_adapter:MyAdapter"
```

如果是仓库内置示例适配器，可以直接使用内置策略名：

```toml
[calendar]
sources = ["eastmoney", "jisilu"]
```

也可以组合自己的适配器和内置示例适配器：

```toml
[calendar]
sources = ["my_source", "eastmoney", "jisilu"]

[adapters.my_source]
class = "my_package.my_adapter:MyAdapter"
```

也可以运行时指定：

```bash
python main.py --source my_source
```

## 适配器职责边界

适配器负责：

- 请求或读取原始数据。
- 处理分页、鉴权、字段清洗。
- 将原始字段转换为 `BondEvent`。
- 返回 `AdapterResult`，包含原始条数和标准事件列表。

核心日历生成器负责：

- 根据配置生成标题。
- 根据配置生成 UID。
- 根据配置添加提醒。
- 写入稳定排序后的 `kzz.ics`。

这样新增数据源时，不需要改 ICS 生成逻辑。
