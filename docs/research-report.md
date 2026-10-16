# 首轮选品调研报告

**市场**：中国供应链到新加坡  
**研究截点**：2026-09-06  
**结论性质**：桌面研究与待验证假设，不是采购批准

**2026-10-16 口径澄清**：本报告是在 9 个初始人工方向中对线缆整理做的定向补样，不是全市场选品结果。40 条为 Amazon 与 Lazada 各 20 条历史搜索样本；原先“需求成立/本地需求明确”的表述过强，现限定为供给与历史交易线索，不能据此证明拟售套装的需求缺口、盈利能力或优于其他方向。

## 执行摘要

首轮更值得验证的是小、轻、非强监管、能在 10 秒内演示价值的通用品，而不是截图中最显眼的 IP 潮玩或健康品。当前优先方向是桌面线缆整理、折叠桌面收纳和原创/公版的模块化包饰；可折叠手持风扇有新加坡场景适配，但锂电运输、认证和同质化使其只能列入观察。

2026-09-06 获批后的补充采样记录：`cable management` 在 Amazon SG 匿名搜索约有 189 个结果；Lazada 后续匿名访问成功，页面显示约 16,313 个广义结果，Best Match 前 20 的中位标价为 S$3.27、中位累计销量为 438。这些是已有供给和链接历史交易信号；大量低价、跨境直发和多规格链接提示竞争压力，尚不能证明拟售套装在新加坡的需求缺口。Shopee 仍要求登录，未绕过。三个相近供应挂牌参考为 US$2.26（MOQ 500）、US$2.45-2.47（MOQ 20）和 US$2.87-3.12（MOQ 100），但均不是含运费正式报价。更新后该候选仍为 `WATCH`，不批准采购。

运行 `PYTHONPATH=src python3 -m sg_product_research.cli` 后，以生成的 `generated/ranking.md` 为准。现有成本、运费和零售价都是压力测试假设，必须通过供应商与本地平台采样替换。

## 已观察事实

- 2026-09-06 抓取的 Amazon SG Best Sellers 页面说明榜单基于销售且频繁更新；电脑类可见线缆保护产品排名第 3、桌面支架排名第 5，办公类可见旅行笔记本排名第 4。
- 同一页面健康护理前列以补充剂为主，说明有需求信号，但 HSA 明确要求经销者承担安全、质量、标签和宣称责任。首版资源不足时应排除，而不是因榜单高就进入采购。
- 用户截图提出的“多个高表现广告反复出现”比单条广告更可靠；该逻辑已进入证据置信度和人工采样 SOP。
- 新加坡海关 2026 年页面说明：进口商品受 Customs Act、GST Act 与 RIEA 管理；除酒、烟、机动车、石油产品等应税品外，其他商品通常为非应税但需考虑 GST；进口前应核对 HS 编码、管制状态和许可。
- 海关页面指出非管制、非应税且 CIF 不超过 S$400 的邮政或空运件可能适用进口 GST relief/permit waiver；这不等同于卖家端一定没有 GST 义务，低价值商品的 Overseas Vendor Registration 仍需按 IRAS 和主体结构复核。
- Amazon SG 的前 8 个可量化样本价格为 S$14.65-S$58.62；线夹、套管、线槽、理线盒和大型桌下托盘并非同规格，不能直接平均为目标售价。
- Amazon 页面当时显示配送地为美国，故价格以 SGD 展示不等于每件都能按该条件配送到新加坡地址；正式测试须用新加坡收货地址复核。
- Lazada Best Match 前 20 标价为 S$1.16-S$15.09；中位价 S$3.27，20 条均显示累计销量且中位数为 438，最高为 5.1K。该快照记录的是链接累计值，多规格链接不能解释为单一 SKU 的近期销量，更不能直接外推为拟售套装的需求。
- Lazada 前 20 中 5 条显示从新加坡发货，14 条显示中国或香港，1 条未显示地点；页面快照未暴露卖家名称、数值评分或明确 Sponsored 标签，因此原始样本保留为空或 `not_observed`，不作推断。
- Made-in-China 与 Global Sources 的供应挂牌显示供给充足，但 MOQ 从 20 到 500 不等，且缺少统一规格、包装重量、贸易条款和时效，不能直接替换当前成本假设。

## 候选判断

| 方向 | 当前判断 | 为什么 | 下一个最小验证 |
|---|---|---|---|
| 通用线缆整理套装 | 优先补证 | 已有定向商品与交易线索，轻小、易演示仍属研究假设；低价单品竞争强 | 验证“桌面场景组合包”是否有区别于单件的付费需求；补 Shopee 样本与 3 家同规格报价 |
| 折叠桌面收纳架 | 优先补证 | 本地榜单邻近需求、无电池 | 测包装体积与承重退货风险 |
| 原创模块化包饰 | 小心验证 | 内容传播强、物流好 | 排除任何角色仿制；测 3 套原创视觉与点击率 |
| 可折叠手持风扇 | 观察 | 气候适配、展示性强 | 锂电专线全包价、IEC/安全资料、SG 关键词趋势 |
| 吸尘器宠物毛刷头 | 观察 | 痛点明确 | 接口兼容矩阵与预期退货率 |
| 可重复防潮盒 | 观察 | 湿热场景合理 | 本地搜索量、耗材复购与海运重量成本 |
| IP 毛绒挂件 | 阻断 | 未授权时 IP 风险不可接受 | 只有拿到可验证授权链才重开 |
| 保健补充剂 | 阻断 | 质量、标签、宣称责任超出首版能力 | 暂不投入 |

## 90 天验证节奏

1. **第 1-2 周，补数据**：每个方向记录 Amazon/Shopee/Lazada 前 20，Google Trends SG 近 12 月与 90 天，TikTok SG 同类素材重复度；每项至少两次采样。
2. **第 2-3 周，供应链**：每个入围品询 3 家，统一规格获取 EXW、包装尺寸重量、MOQ、交期、质检、认证和侵权保证。
3. **第 4-6 周，小批量**：只对 `TEST` 候选下 20-50 件；准备 3 个卖点角度，不因单条素材胜出就加库存。
4. **第 7-12 周，复购与放量**：按售罄、退款、广告后贡献毛利、评价缺陷率决定停、改或补货。

## 需要业务方审批

已完成无需登录的 Amazon 20 条、Lazada 20 条样本与 3 个供应公开挂牌参考。尚未执行：注册/登录平台账号、发送供应商询盘、购买第三方数据、调用付费 API、自动抓取受限页面、采购样品、投放广告。当前可继续使用公开来源补证；若要补齐 Shopee 或取得正式报价，则需要业务方另行批准账号使用和发送询盘。密码和验证码应由业务方直接在浏览器输入，不要发给项目成员或记录在仓库。

## 官方与公开来源

- [Amazon Singapore Best Sellers](https://www.amazon.sg/gp/bestsellers)
- [TikTok Creative Center](https://ads.tiktok.com/business/creativecenter/inspiration/popular/products/pc/en)
- [Google Trends Singapore](https://trends.google.com/trends/explore?geo=SG)
- [data.gov.sg](https://data.gov.sg/)
- [Singapore Customs Import Procedures](https://www.customs.gov.sg/doing-business/import-operations/import-procedures/import-procedures-overview/)
- [Singapore Customs Controlled and Prohibited Goods](https://www.customs.gov.sg/doing-business/import-operations/import-procedures/controlled-and-prohibited-goods-for-imports/)
- [IRAS GST and Digital Economy](https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/gst-and-digital-economy)
- [HSA Health Supplements](https://www.hsa.gov.sg/health-supplements/overview)
