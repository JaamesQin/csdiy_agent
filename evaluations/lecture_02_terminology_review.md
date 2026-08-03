# Lecture 2 中文术语审核

审核日期：2026-08-02

## 采用的规范

| 英文 | StudyKit 用语 | 说明 |
| --- | --- | --- |
| gradient descent | 梯度下降 | 保留通用译法 |
| stochastic gradient descent | 随机梯度下降（SGD） | 首次出现给出缩写 |
| mini-batch SGD | 小批量 SGD / mini-batch SGD | 避免把严格 SGD 与小批量实现完全等同 |
| full-batch gradient descent | 全批量梯度下降 | 避免含糊的“标准梯度下降” |
| batch / batch size | 批次（batch）/ 批大小（batch size） | 中文为主，保留工程中常用英文 |
| forward pass | 前向传播（forward pass） | 与“反向传播”保持配对 |
| backpropagation | 反向传播 | 专指利用链式法则计算梯度，不等同于参数更新 |
| computation graph | 计算图 | 保留通用译法 |
| directed acyclic graph | 有向无环图（DAG） | 首次出现可使用全称，后续使用 DAG |
| automatic differentiation | 自动微分 | 不与符号微分或有限差分混用 |
| differentiable programming | 可微编程 | 保留国内技术资料中的常见简称 |
| gradient summation at branches | 分支处的梯度求和 | 不使用“梯度累加”，以免与跨批次 gradient accumulation 混淆 |
| gradient accumulation | 梯度累加 | 仅用于 PyTorch `.grad` 跨多次 `backward()` 累积等语境 |
| loss function / objective function | 损失函数 / 目标函数 | 损失衡量预测误差；目标函数是实际优化的标量，可包含损失和正则项 |

## 修改结果

- 统一了 batch、batch size 与 mini-batch 的中文和英文展示。
- 澄清了严格 SGD、mini-batch SGD 和全批量梯度下降的关系。
- 将 DAG 分支处的 “gradient accumulation” 改为 “gradient summation”，避免与框架中的梯度累加混淆。
- 补充损失函数、目标函数、批次、批大小和小批次的 glossary 定义。
- 保留 MLP、SGD、DAG、ReLU、PyTorch API 名称及代码变量等通用缩写或英文。

结论：StudyKit 的中文术语已达到内部一致性要求。复杂公式符号和矩阵方向随后已在 `lecture_02_math_review.md` 中完成单独审核。
