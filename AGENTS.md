# 本仓库工作约定

本仓库维护 interview-questions skill，面向简历定制的招聘面试准备。保留用户已确认的面试顺序、可直接照读的问题、分层追问、技术参考答案与证据边界。

- skill 的唯一源码是 skills/interview-questions；安装位置默认是 $CODEX_HOME/skills/interview-questions，CODEX_HOME 未设置时为 ~/.codex/skills/interview-questions。
- 用户已要求本仓库 skill 创建后安装，每次更新后同步更新安装版本。修改 skill 任意文件后，执行 python3 scripts/sync_skill.py，再执行 python3 scripts/sync_skill.py --check；不能只提交源码而声称安装已更新。
- 安装目标有本地改动或来源冲突时保留原件，先检查差异，不能静默覆盖。同步脚本不修改其他 skill。
- 提交前运行 python3 scripts/check_skill.py 和 python3 -m unittest discover -s tests -v。结构检查与问题质量的语义评审分别记录。
- 用真实简历验证时，原件、提取文本、候选人姓名、联系方式与个人面试稿留在本地授权输出目录；公开仓库只放合成用例。
- 对问题质量的修改，用 evals/cases.json 中相关场景验证，记录实际产物和发现；不能用字段齐全证明面试质量。
- 仓库规则只适用于本仓库，不作为使用 skill 时修改其他项目的规则。
