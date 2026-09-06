# SG Product Research

面向“中国供应链到新加坡”的零依赖选品研究项目。它把公开免费数据、供应链假设、合规/IP 门槛和单位经济模型放进同一条可复现流程。

## 快速开始

要求 Python 3.8+：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m sg_product_research.cli
```

结果生成到 `generated/ranking.csv` 和 `generated/ranking.md`。

## 本地管理后台

在项目根目录启动：

```bash
PYTHONPATH=src python3 -m sg_product_research.server
```

浏览器访问 [http://127.0.0.1:8765](http://127.0.0.1:8765)。后台可查看候选排名、平台访问状态和 Lazada 摘要；点击候选行末的编辑按钮可修改评分、风险与单位经济参数，保存后会同步更新 `data/candidates.csv` 和 `generated/` 下的排名结果。

后台默认只监听本机且没有账号系统，不应使用 `--host 0.0.0.0` 暴露到局域网或公网。停止服务时，在启动它的终端按 `Control+C`。

## GitHub Pages 托管

仓库包含 `.github/workflows/pages.yml`，推送到 GitHub 的 `main` 分支后会自动构建并部署静态只读版。Pages 版本可查看排行和证据状态，但不能直接修改 CSV 或重算；需要先在本地后台更新数据，再提交并推送，网站才会刷新。

首次使用时，在 GitHub 仓库的 **Settings → Pages → Build and deployment** 中把 Source 设为 **GitHub Actions**。本地预览静态构建：

```bash
PYTHONPATH=src python3 scripts/build_pages.py
python3 -m http.server 8000 --directory _site
```

然后访问 [http://127.0.0.1:8000](http://127.0.0.1:8000)。

## 文件说明

- `data/candidates.csv`：候选、证据、评分和成本假设。
- `data/sources.csv`：免费数据源、采样频率与局限。
- `data/samples/`：带时间戳的平台样本、访问状态和供应公开挂牌。
- `docs/research-report.md`：首轮研究结果与 90 天计划。
- `docs/methodology.md`：评分、利润与门槛定义。
- `docs/data-playbook.md`：每周人工采样与供应商询价 SOP。
- `docs/supplier-inquiry.md`：待审批发送的中英文询盘。
- `src/sg_product_research/`：评分与报告生成代码。

## 数据纪律

首版候选中的平台外评分和成本均为待验证假设，不应直接用于采购。每次更新要保留来源、地区、日期和原始证据；任何 `BLOCK` 项都必须先解决对应风险，不能通过调高趋势分绕过。
