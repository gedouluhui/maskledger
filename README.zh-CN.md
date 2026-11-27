# MaskLedger

**看清分割标注在转换过程中丢掉的结构。**

[在线交互演示](https://gedouluhui.github.io/maskledger/) · [English](README.md) · [本地交互示例](docs/index.html)

比较转换前后两份 COCO 实例分割 JSON，定位填孔、区域连接、小结构消失、像素偏移，以及实例缺失／新增、类别和 crowd 变化。无需模型、GPU、数据库或上传图片。

## 快速运行

```sh
git clone https://github.com/gedouluhui/maskledger.git
cd maskledger
python -m pip install .
maskledger demo --out demo-output
```

打开 `demo-output/index.html`。内置环形、孤岛、细线等样本全部自制，报告来自真实计算，不是预写答案。下载并打开 `docs/index.html` 可免安装查看已生成示例。

```sh
maskledger compare before.json after.json --out conversion-report
```

默认要求 annotation ID、image ID 与尺寸对应。标注顺序不同不影响结果；不会靠“形状最相似”悄悄补配对。转换改变 ID 时，可传 `--id-map mapping.json`：

```json
[{"reference_id": 7, "candidate_id": 42}]
```

映射必须一对一，未映射项明确记为缺失或新增。输出目录必须不存在，不覆盖原数据。

## 如何读报告

参考、候选、差异三幅图与指标来自同一次审计。蓝色是删除像素，橙色是新增像素，灰色是保留区域；指标使用全分辨率，预览可能缩小。

IoU、面积、像素增减之外，报告还比较连通分量和孔洞。前景使用 8 邻接、背景使用 4 邻接；空并集的 IoU 是 `null`，不伪装为满分。最多 80 项有图片预览，所有数值发现仍完整保留。

退出码：`0` 完整且等价；`1` 完整但有变化；`2` 无法完成可靠比较。`demo` 的退出 0 表示正反对照按预期运行，并不表示变化样本“没有变化”。

## 边界

仅支持同一图像坐标空间的 COCO polygon 与压缩／非压缩 RLE。首版不直接导入 YOLO 文本、不猜测实例身份、不读取原图检查 EXIF，不检查 bbox／关键点，也不评估模型或源标注是否正确。COCO polygon 按其光栅化语义求并集，不能冒充原生带孔多边形。

完整预算、Python API、测试入口和已有替代工具见英文说明。资源限制是工作量约束，不是恶意媒体沙箱或进程内存上限保证。报告中含类别名和掩膜预览，分享真实数据前请自行检查。

自有代码与样本使用 MIT；依赖保持各自许可证。没有捆绑外部数据、模型或私有文件。核心曾经过独立审查及修复复核；0.1.1 增加事务性报告发布与可重建、可在全新环境重跑安装后 CLI 的源码包，这两项新增尚未经新一轮独立复审。尚未进行外部真实用户验证。

## 快速开始与支持状态

### 问题
发现两个 COCO 实例分割标注文件之间转换时丢失的像素与拓扑结构。

### 安装
```sh
python -m pip install .
```

### 成功命令
```sh
maskledger demo --out demo-output
```
预期：真实审计器复现已知的变更和未变更对照；退出码 0。

### 故意失败命令
```sh
maskledger compare demo-output/reference.json demo-output/candidate.json --out conversion-report
```
预期：合成变更标注产生 changed 报告；退出码 1。

### 证据与覆盖边界
证据包括手写拓扑用例、对照 pycocotools 的压缩 RLE 检查、真实 CLI 输出与退出码、恶意标签文本、精确大整数 ID 浏览器数据、畸形 JSON、原生光栅限制和变异检查。没有转换日志时，差异不会自动被判定为错误标注或转换器缺陷。

### 支持状态
版本 0.1.1 支持 Python 3.11+ 和文档中的 COCO polygon/RLE 子集。此版本的报告发布是事务性的，但新的独立复审和真实用户验证仍待完成。维护为尽力而为，不提供 SLA。

### 限制
不支持直接导入 YOLO/LabelMe、推断匹配、图像内容检查、自动修复、语义真值和模型质量。拓扑采用 8 连通前景和 4 连通背景；工作负载保护不是安全沙箱或硬内存保证。
