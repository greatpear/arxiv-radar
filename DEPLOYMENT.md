# 论文雷达部署配置

本仓库通过 GitHub Actions 自动运行，每天北京时间 10:00（UTC 02:00）开始执行。
GitHub 的定时任务可能排队，邮件在检索、评分和摘要生成完成后发出。

追踪方向：

- 语义通信与深度联合信源信道编码。
- 水声通信、信道估计、均衡及调制解调。
- 光无线通信、水下无线光通信、信道建模与散射。
- 声光融合通信及水下声光混合网络。
- 面向水声、光信道的智能语义传输。

检索分类为 `cs.IT+eess.SP+physics.optics+cs.NI`，每天最多展示 20 篇论文，
摘要使用中文。当天没有新论文时也发送通知。收发邮箱与授权码只保存在
GitHub Actions Secrets 中；本地 `.env` 不会提交。

## 管理

- `Actions → Daily Paper Sender`：定时任务，也可手动运行。
- `Actions → Test - Daily Paper Sender`：检索最近 5 篇论文以验证完整流程。
- `Actions → Deployment Check`：验证 Linux 依赖、回归检查和论文源连接，不发送邮件。
- `Settings → Secrets and variables → Actions → Variables`：修改研究兴趣
  `RETRIEVER_TARGET`、邮件篇数 `MAX_PAPER_NUM`、摘要语言 `LANGUAGE`
  和空结果通知 `SEND_EMPTY`。
- `Settings → Secrets and variables → Actions → Secrets`：修改收件人
  `RECEIVER`、发件人 `SENDER`、SMTP 服务器 `SMTP_SERVER`、端口 `SMTP_PORT`
  及授权码 `SENDER_PASSWORD`。
- 修改运行时间：编辑 `.github/workflows/main.yml` 的 `schedule`，使用 UTC。

默认使用项目原有的本地量化模型，无需购买大模型 API 服务。首次运行会下载模型，
后续通过 Actions 缓存复用。

## 部署修正

- 465 端口直接使用 SSL，其他端口先启用 STARTTLS，连接超时为 30 秒。
- 程序不再把包含邮箱授权码的命令行参数打印到日志。
- 测试工作流使用已配置的论文分类，限定为 5 篇。
- Python 固定为 3.11，依赖使用 `uv.lock`，Linux 和 Windows 使用预编译 CPU 推理库。
- 工作流运行当前仓库的代码，保持以上部署配置。

回归检查：

```sh
uv run --locked python -m unittest discover -s test -p test_deployment.py -v
```
