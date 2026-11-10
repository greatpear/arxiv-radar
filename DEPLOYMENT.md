# 论文雷达部署配置

本仓库通过 GitHub Actions 自动运行，目标为每天北京时间 10:00 推送。
每天 09:37（UTC 01:37）提前检索、评分并生成摘要，准备完成后等到 10:00 再发送。
10:07 和 10:27（UTC 02:07、02:27）再次检查：当天已完成则跳过，漏触发或失败则补跑。
11:11 至 22:11（UTC 03:11 至 14:11）每小时继续检查一次，避免上午的触发全部遗漏后整天不再补跑。
GitHub 官方说明定时任务可能延迟，整点高负载时甚至可能丢弃，因此此配置减少漏发，不能保证准点送达。
若生成摘要在 10:00 后才完成，会立即发送；邮件实际到达时间还取决于邮件服务。
参见 [GitHub 定时调度说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

每天使用北京时间的日期去重。SMTP 接受邮件后才写入 `.github/daily-delivery.json` 并提交，
发送失败不记为完成，留待补跑。补跑读取主分支最新的发送记录，不重复发送已完成的当日报告。
发送成功后若记录提交失败，可从运行的 `daily-digest` 附件恢复记录，再补跑，避免重复邮件。

筛选原则：以语义通信为方法主线，应用场景开放。水声、光、声光融合和其他通信环境均可，
图像、视频、语音、文本、传感数据等信源均可；不把某一种信道、场景或模态设为必要条件。
ResiComp、FAJSCC、MambaJSCC 是方法参照，其中 ResiComp 类学习式抗丢包编解码也作为相关工作保留。

追踪方向：

- 语义通信与 DeepJSCC 编码器、解码器、语义表示和端到端传输方法。
- 任务型语义编码、特征选择、重建或接收端分类/推理，以及多模态语义传输。
- 抗丢包学习式编码、掩码 token、潜变量修复与丢包隐藏。
- 低复杂度与计算量可调、SNR/CSI 自适应、可变码率传输。
- 扩散模型、离散 token 与生成式语义传输。
- 上述方法在水下声学、光、声光混合、常规无线、卫星等场景中的应用。

检索分类为 `cs.IT+eess.SP+eess.IV+cs.CV+cs.MM+cs.LG+cs.CL+eess.AS+cs.NI`，覆盖通信、视觉、多媒体、语言、语音和学习等领域。
先用 RSS 标题和摘要过滤，再请求目标论文元数据，避免对整个视觉/学习分类逐篇调用 API。
只保留方法符合上述要求且相关性分数至少为 70 的论文，每天最多展示 20 篇，数量不足时不补入无关论文。
ResiComp 属于抗丢包的学习式图像压缩，不要求论文必须出现“语义通信”或“JSCC”字样。
普通光链路、通感一体化、水声均衡/信道估计、普通无损链路压缩、材料和量子物理论文，
若未实质采用或改进语义通信/学习式通信编码方法，则不构成匹配。
摘要使用中文。没有通过筛选的论文时只发送空结果通知。收发邮箱与授权码只保存在
GitHub Actions Secrets 中；本地 `.env` 不会提交。

## 管理

- `Actions → Daily Paper Sender`：定时任务，也可手动补跑；当天已完成时只检查记录，不再次发信。
- `Actions → Test - Daily Paper Sender`：按通信主题检索最近 5 篇候选论文，执行相同的领域与分数筛选，
  默认只生成预览；在运行结果的 `radar-preview` 中下载 HTML 和 JSON。勾选 `send_email` 才发送测试邮件。
- `Actions → Deployment Check`：验证 Linux 依赖、回归检查和论文源连接，不发送邮件。
- `Settings → Secrets and variables → Actions → Variables`：修改研究兴趣
  `RETRIEVER_TARGET`、主题检索式 `TOPIC_QUERY`、最低分 `MIN_SCORE`、邮件篇数 `MAX_PAPER_NUM`、
  摘要语言 `LANGUAGE` 和空结果通知 `SEND_EMPTY`。
- `Settings → Secrets and variables → Actions → Secrets`：修改收件人
  `RECEIVER`、发件人 `SENDER`、SMTP 服务器 `SMTP_SERVER`、端口 `SMTP_PORT`
  及授权码 `SENDER_PASSWORD`。
- 修改运行时间：编辑 `.github/workflows/main.yml` 的 `schedule`，使用 UTC。

默认使用项目原有的本地量化模型，无需购买大模型 API 服务。首次运行会下载模型，
后续通过 Actions 缓存复用。

## 部署修正

- 465 端口直接使用 SSL，其他端口先启用 STARTTLS，连接超时为 30 秒。
- 程序不再把包含邮箱授权码的命令行参数打印到日志。
- 测试工作流按通信主题获取候选论文，与每日任务使用相同的筛选门槛；0 分论文不会进入邮件。
- 模型使用稳定的主题编号评分，缺失主题、添加主题或无效分数均不会形成推荐。
- Python 固定为 3.11，依赖使用 `uv.lock`。Windows 使用预编译 CPU 推理库；
  Linux 首次从源码构建 CPU 推理库并缓存，避开预编译库的系统兼容问题。
- 工作流运行当前仓库的代码，保持以上部署配置。

回归检查：

```sh
uv run --locked python -m unittest discover -s test -p test_deployment.py -v
uv run --locked python -m unittest discover -s test -p test_daily_delivery.py -v
```
