"""Offline authoring checkpoint for the assigned CS188 standard-build units.

This is a course-scoped authoring aid: it creates only 01--03 in the assigned
unit directories.  It deliberately does not create audits, final kits, or
build summaries.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path("outputs/ucb-cs188-spring-2026/69fe955521460db981668f0669d17dbd26c12fd4c7638c6e5488ace3e99d4511/courses/ucb-cs188-spring-2026/units")
SRC = Path("data/sources/ucb-cs188-spring-2026")
SID = "ucb-cs188-spring-2026-{u}-material"
SOURCE_SHA = {
 "lecture-04":"ad5fdba55f04c5eb6b05ac91aca22be6affcd489b10c34a6f3e0df12b89cc0be",
 "lecture-08":"6dcb2f4e407f6640f6b1f95cbe12d16e3d4773f4c907eb20805048840ee52cf1",
 "lecture-12":"49172b7a248a22dd32a911256db70d08dde16754a94b69a5e289ff4d1ad6a06b",
 "lecture-16":"c4563cc42087717373361f851c6eae23a96ab4a0838a8d3b3d3d516f7edfbb65",
 "lecture-20":"64dc1d9c47299b8bab8dd44a69dd311b6cf94caeb56cd107f768c47ee7087bdc",
 "lecture-24":"67ed527f04a28a7d0d08f4f84cc6afc14105731c6017eb1404f8efce666d7522",
 "lecture-28":"6695661d3f8fc2971ae8dccbf2f2d613482c4b68d41d8cb44b93fed4dd1d0e99",
}
UNITS = {
 "lecture-04": ("局部搜索", [26,27,28,31,35,40,41], [
  ("p1","基础","给定四个状态 A、B、C、D 的评价分别为 3、7、6、7；A 的邻居是 B、C，B 的邻居是 A、D，D 没有更高邻居。从 A 开始按严格爬山写出状态序列、每次比较的候选值和停止理由；规定同值不移动。若改为允许一次横向移动，再说明从 B 会到哪里以及为什么需要横向次数上限。", "列出每个当前状态的全部邻居，严格比较评价值；横向移动的价值与原值相等。", "逐轮表格、最终状态、横向移动后的边界分析。", [27,29,30]),
  ("p2","应用","一个 5 列棋盘用向量 (2,5,1,4,2) 表示每列皇后所在行。冲突定义为同一行或行差等于列差的一对皇后，每一对只计一次。计算当前冲突对；然后只改变第 3 列，分别试行 1、2、3、4、5，给出每个候选的冲突数并选择最低者，平局取行号小者。", "按两列距离 d 检查行差是否为 0 或 d，并只重新计算涉及第 3 列的对。", "冲突对清单、五个候选值、确定的移动及平局规则。", [28]),
  ("p3","综合","局部束搜索保留 K=2 个状态。当前状态 U、V 的后继评价集合分别是 U:{4,9}、V:{8,5}；把四个后继合并后保留两个。另有退火移动从评价 10 到 7，温度分别为 5 和 0.2。分别写出束搜索结果，并解释两种温度对较差移动接受概率的方向，不计算指数。", "束搜索在所有当前状态的后继中统一排序；退火只在变差时使用温度。", "排序表、保留状态、温度变化的方向性解释。", [31,32,35]),
  ("p4","综合","固定三个客户 c1=(1,0)、c2=(3,0) 由机场 A 服务，机场 A 当前为 (0,0)，只允许 x_A=x 变化且 y_A=0。写出平方距离目标 f(x)，求 x=0 的导数，并用步长 0.25 做一次 x←x−αf'(x) 更新；说明若更新后最近机场归属改变，下一轮必须先做什么。", "固定本轮客户分配后逐项展开平方距离；梯度下降沿负导数更新。", "目标函数、导数、数值更新和重新分配条件。", [40,41]),
 ]),
 "lecture-08": ("不确定性与效用", [3,5,8,10,15,25,30], [
  ("p1","基础","MAX 节点在行动 A、B 中选择。A 的 chance 后继为 (概率 0.25,效用 4)、(0.75,效用 8)；B 的 MIN 后继效用为 5、9。分别计算 A 的期望效用和 B 的 MIN 值，并按根节点规则选择行动。", "chance 是概率加权平均，MIN 取最小后继；两者不是同一回传规则。", "两种回传计算、根选择及每个概率乘积。", [3,5,8]),
  ("p2","应用","天气 W 有 sunny=0.5、rain=0.3、storm=0.2；行动 walk 的效用分别为 10、2、-8，行动 bus 的效用恒为 5。计算两个行动的期望效用并选择；若观测到已知 storm，重新选择并说明这是改变了哪一个输入。", "先按全分布加权，再在已知天气时使用条件情形而不是继续平均全部天气。", "两次期望计算、选择和信息改变的说明。", [10,15,25]),
  ("p3","综合","一个对手 0.6 的概率选择确定动作（其两个后继效用为 3、11，按 MIN 取 3），0.4 的概率随机选择，随机分支两个后继效用为 5、9。对根行动 X 计算该混合对手的期望回传；写出若误把对手当纯 MIN 会得到什么，并比较两者。", "先在每种对手行为内回传，再按行为概率加权；概率不能被忽略。", "分支树数值、混合值、纯 MIN 对照和误差方向。", [5,15,20]),
 ]),
 "lecture-12": ("强化学习 II", [2,5,8,12,18,24,27], [
  ("p1","基础","学习器在状态 s0 执行动作 a 后观察到奖励 3 和下一状态 s1；当前 Q(s0,a)=2，α=0.5，γ=0.8，s1 的 Q 值为 6 和 1。按 Q-learning 的 target=r+γ max Q(s1,·) 更新一次；若 s1 是终止状态且未来项定义为 0，再算一次。", "先选下一状态最大 Q，再乘折扣；终止状态不加未来价值。", "两个 target、两个更新值和终止条件的差异。", [5,8,24]),
  ("p2","应用","一个两动作环境的当前策略在 s0 选 East；ε-greedy 中 ε=0.2，合法动作只有 East、North，随机探索均匀分配。计算两动作概率；再将 ε 改为 0.8 重算，并说明为什么训练后期常降低 ε。", "探索概率先分到所有合法动作，再加到策略动作的利用概率。", "两组精确概率、计算式和训练阶段解释。", [12,18,27]),
  ("p3","综合","四个 episode 的回报为 [6, 8, 10, 4]，候选策略 P 在这四次分别为 [7, 7, 9, 5]，候选 Q 为 [5, 10, 11, 3]。计算三组均值，选择样本均值更高者；然后指出这个选择不能证明真实期望回报更高的至少一个原因，并给出应继续收集的证据。", "逐项求和除以 4；样本评估可能有方差，不能把有限 episode 当总体。", "均值、选择、统计不确定性和后续测量方案。", [8,25,27]),
 ]),
 "lecture-16": ("贝叶斯网络抽样", [2,6,10,16,21,25,30,34], [
  ("p1","基础","变量 C 的概率为 red=0.5、green=0.3、blue=0.2。用一个 u=0.76 按累计区间进行一次 prior sample，并写出三个半开区间。", "按累计概率从 0 开始划分区间；u 落在哪个区间就返回哪个类别。", "区间边界、u 所在区间和样本结果。", [2,6,10]),
  ("p2","应用","五个 prior sample 的 W 结果为 [true,false,true,true,false]。估计 P(W=true)；若查询改为 P(W=true | R=true)，五个样本中只有第 1、3、4 个的 R=true，且对应 W=[true,false,true]，用这些样本估计条件概率，并说明拒绝其余样本的原因。", "无条件估计用全部样本计数；条件估计只保留证据匹配的完整样本。", "两个频率、保留索引和证据筛选解释。", [10,16,34]),
  ("p3","综合","在似然加权中，证据变量 E=e 的 CPT 概率为 0.2；一次样本对另外三个变量完成 prior sampling，且它们不是证据。计算该样本权重。再给第二样本同样结构但 P(E=e|父状态)=0.8，比较两者对加权频率的影响；说明若证据是固定节点，不能把它重新采样。", "权重乘以证据在当前父状态下的 CPT 概率；非证据变量照常采样。", "两个权重、影响比较和固定证据说明。", [21,25]),
 ]),
 "lecture-20": ("机器学习 I：决策树与线性回归", [2,9,24,28,32,40], [
  ("p1","基础","有四封训练邮件：属性 contains_free 为 0 的两封标签 ham，属性为 1 的两封标签 spam。用该属性作为根节点，写出两个叶子的标签和一封新邮件 contains_free=1 的预测路径；说明这是分类而不是回归。", "根测试按属性值分支，叶节点使用该分支的训练标签；分类输出离散标签。", "树、路径、预测标签和任务类型。", [9,24,28]),
  ("p2","应用","候选属性 P 的加权剩余熵为 (2/10)B(0)+(8/10)B(1/4)，属性 Q 的加权剩余熵为 (5/10)B(1/2)+(5/10)B(1/2)，根熵为 1。保留 B(p)=-p log2 p-(1-p)log2(1-p)，计算两项 gain 的表达式并选择根属性。", "gain=根熵−加权剩余熵；先计算每个二元熵，再比较。", "熵值、两项 gain 和选择理由。", [30,32]),
  ("p3","综合","数据集有 6 个 train、2 个 validation、2 个 test 样本。两个候选树在 validation accuracy 分别为 1/2 和 2/2，最终选第二棵；它在 test 上预测 [ham,spam]，真实标签 [spam,spam]。计算最终 test accuracy，并说明若根据 test 结果再次选树会破坏什么评估边界。", "validation 用于选择，test 只用于最后一次泛化估计。", "三组数据用途、accuracy 和泄漏风险。", [24,25]),
 ]),
 "lecture-24": ("语言模型 I", [3,8,12,16,20,30,35], [
  ("p1","基础","对上下文 “I drink hot ___” ，模型给 tea=0.6、coffee=0.3、water=0.1。按最大条件概率选择下一词；若真实下一词是 water，写出这次评估使用的似然值。", "预测选最大条件概率，但评估真实词时读取真实词对应的概率。", "选择、真实词概率和两者区别。", [3,8,12]),
  ("p2","应用","训练语料中 P(door|the)=0.002，P(door|close the)=0.04。对上下文 “close the ___” 分别写 bigram 和 trigram 使用的历史，并给出各自对 door 的概率；再给一个超过固定 n 个词的上下文信息，说明它为何会被低阶模型截断。", "bigram 只保留一个前词，trigram 保留两个前词；不能把更早词带入固定窗口。", "两个条件概率、历史窗口和截断信息。", [16,20]),
  ("p3","综合","对词序列 “we study probabilistic models” 预测最后一个词：若 4-gram 计数为 0，3-gram 条件计数为 12，2-gram 条件计数为 50，说明一个回退策略会保留哪些后缀、何时继续回退；若所有候选上下文计数都为 0，给出一个明确的平滑/回退处理而不是猜测原词。", "回退逐步缩短历史并记录信息损失；零计数必须由已声明的平滑或未知词策略处理。", "回退序列、保留/丢弃词、零计数策略。", [20,30]),
 ]),
 "lecture-28": ("综合：规划、不确定性与学习", [2,12,20,45,50,60,70], [
  ("p1","基础","机器人在路口有路线 A（预计 2 步但前方不可见）和路线 B（预计 4 步且当前可见）。分别写出 planning、uncertainty、learning 在这次决策中各自需要的输入；若传感器发现 A 前方有障碍，指出先更新哪一项输入并重新比较什么。", "planning 比较后果，uncertainty 表示未知状态或结果，learning 用过去经验更新估计；传感器先改变当前状态/信念。", "三栏输入、信息更新顺序和重新比较的目标。", [2,12,45]),
  ("p2","应用","一个三字母横向词槽线索为“猫叫声”，候选为 MEW、MIA；交叉字母要求第二位为 E。列出候选生成、交叉过滤后的集合和最终可接受候选；若删除交叉字母约束，说明输出应如何标记为未完成而不是任意选词。", "先保留满足长度/线索的候选，再应用显式交叉约束；缺约束时只能保留不确定性。", "候选集合、过滤过程和缺失约束的边界说明。", [20,30,60]),
  ("p3","综合","候选器在 20 个线索上 Top-1 正确 8 个，Top-1000 覆盖 18 个；其中只有 12 个最终组合成完整谜题。计算 Top-1 accuracy、Top-1000 recall 和端到端成功率；若把 closed-book 换为 open-book，列出至少两个必须重新测量的阶段指标，并解释为什么不能只看候选器指标。", "分别用 8/20、18/20、12/20；端到端指标还包含约束解析/组合阶段。", "三个数值、阶段指标和链路分析。", [50,60,70]),
 ])
}

def cite(u, p):
    sid=SID.format(u=u)
    return {"source_id":sid,"chunk_id":f"{sid}-p{p:03d}","anchor":{"type":"page","value":p}}

def main():
    for u,(title,pages,pracs) in UNITS.items():
        rows=[json.loads(x) for x in (SRC/u/'chunks.jsonl').read_text().splitlines()]
        by={r['anchor']['value']:r for r in rows}; pages=[p for p in pages if p in by]
        sid=SID.format(u=u); chunk_hash=hashlib.sha256((SRC/u/'chunks.jsonl').read_bytes()).hexdigest()
        evidence=[]
        for i,p in enumerate(pages,1):
            evidence.append({"id":f"ep-{i:02d}","requirement":f"从第 {p} 页可见材料提取并解释与“{title}”相关的定义、机制或计算规则。","anchors":[cite(u,p)]})
        ep={"schema_version":"0.2","quality_mode":"standard","course_id":"ucb-cs188-spring-2026","course_version":"spring-2026","unit_id":u,"title":title,"source":{"source_id":sid,"source_sha256":SOURCE_SHA[u],"chunks_sha256":chunk_hash,"anchor_type":"page"},"visible_source_boundary":"本 checkpoint 只使用 chunks 中的可见讲义文字；隐藏/overlay 层不作为学习者证据。","evidence":evidence,"page_coverage":{"cited_pages":pages,"page_count":len(rows)},"unsupported_or_omitted":[]}
        lo=[]
        for i,p in enumerate(pages[:4],1): lo.append({"id":f"lo-{i}","objective":f"给定一个明确的新情境，能够应用“{title}”在第 {p} 页支持的规则并给出可观察结果。","citations":[cite(u,p)]})
        lc={"schema_version":"0.2","quality_mode":"standard","course_id":"ucb-cs188-spring-2026","course_version":"spring-2026","unit_id":u,"title":title,"learning_objectives":lo,"prerequisites":[{"topic":"概率、状态/动作或基本函数计算（按本单元任务需要）","required_level":"能读取题目给出的对象、数值和条件","citations":[cite(u,pages[0])]}],"outline":[{"order":i,"topic":f"{title}：证据页 {p}","purpose":"从定义到一个可检验的应用。","anchors":[cite(u,p)]} for i,p in enumerate(pages[:4],1)],"core_concepts":[{"name":title,"explanation":"以本单元证据页中的规则处理给定输入，不把讲义示例本身当作唯一题设。","citations":[cite(u,pages[0])]}],"glossary":[],"common_misconceptions":[{"misconception":"把题目要求重新发明完整情境，或把一个局部指标当作端到端结果。","correction":"题面会给出必要对象、状态、条件和验证量；按定义逐步计算并报告边界。","citations":[cite(u,pages[0])]}],"learning_sequence":["先核对题面对象和条件","再应用对应规则计算","最后检查改变条件或端到端指标"]}
        practices=[]
        for idx,(pid,level,q,h,d,ps) in enumerate(pracs,1):
            cs=[cite(u,p) for p in ps if p in by]
            practices.append({"id":pid,"level":level,"mapped_evidence":[f"ep-{min(idx,len(evidence)):02d}"],"question":q,"steps":["圈出题面给出的对象、状态、数值、条件和目标","按本单元规则逐步计算或比较，并写出中间结果","执行题面要求的改变条件/边界检查并报告可观察输出"],"hint":h,"deliverable":d,"expected_evidence":["列出必要输入与规则","给出可复核的中间计算和最终结果","解释改变条件或边界如何影响结果"],"changed_condition":"题面已给出一个确定的改变条件；说明改变前后哪个输入、规则或输出发生变化。","edge_cases":["概率或计数为零时不得除以零或无依据猜测","并列结果要写明 tie-break","终止、缺失约束或证据不足时显式标记"],"evaluation":{"correct":"设置完整、计算可复核、最终结果与边界分析一致且引用相关。","partial":"方法方向正确但遗漏一个中间量或边界条件。","incorrect":"改变了题面规则、缺少必要输入或把局部指标误报为最终成功。"},"citations":cs})
        pf={"schema_version":"0.2","quality_mode":"standard","course_id":"ucb-cs188-spring-2026","course_version":"spring-2026","unit_id":u,"title":title+"：练习流程","practices":practices,"progression":[{"level":"基础","purpose":"直接应用定义与规则"},{"level":"应用","purpose":"在给定新设置中计算并解释"},{"level":"综合","purpose":"比较方法并处理边界或端到端指标"}]}
        out=ROOT/u; out.mkdir(parents=True,exist_ok=True)
        for name,obj in [("01-evidence-plan.json",ep),("02-learning-content.json",lc),("03-practice-flow.json",pf)]:
            (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
        print(u, len(practices), pages)
if __name__=='__main__': main()
