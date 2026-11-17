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

自有代码与样本使用 MIT；依赖保持各自许可证。没有捆绑外部数据、模型或私有文件。核心曾经过独立审查及修复复核，尚未进行外部真实用户验证。
