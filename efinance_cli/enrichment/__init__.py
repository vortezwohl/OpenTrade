"""市场数据技术指标增强层。

该子包位于原始 efinance 数据获取与控制台渲染之间，负责根据命令类型、返回值结构、
数据列能力和用户选择的指标等级，对结果做尽可能丰富但可降级的技术指标补充。

当前阶段优先支持：

- 股票 / 债券 / 期货 / common 的历史 K 线结果增强
- 单标的实时/快照结果的历史回补增强
- 实时列表按范围控制后的最新指标回填
"""

from efinance_cli.enrichment.service import enrich_market_data

__all__ = ["enrich_market_data"]
