# Render 部署准备

`render.yaml` 已配置 Python Web Service：免费实例、禁用自动部署、构建时运行 HTTP 测试、监听 Render 注入的 PORT。`/healthz` 只有两份视频与两份字幕均存在时才返回 200，避免出现“网页上线但不能看视频”的假就绪。

## 当前准备状态

- `review-assets/` 已准备两份真实样片和两份 SRT，合计约 9 MB。
- Render 启动命令：`python server.py --host 0.0.0.0 --port "$PORT" --data-dir review-assets`。
- 原 `data/` 仍被 Git 忽略；不能依赖它出现在远程构建环境中。因此待部署样片另放于 `review-assets/`。
- 没有推送 GitHub、创建 Render 服务或发布公开网址；这些步骤尚未执行。

## 连接后执行

1. 发布前确认允许将这些真实样片放入所选 GitHub 仓库，并通过 Render 公开访问。检查仓库的可见性；不要将媒体放入不希望公开的仓库。
2. 将源码、`render.yaml` 与 `review-assets/` 一起提交并推送至选定分支。不要提交 `data/`、缓存或环境密钥。
3. 在 Render 选择通过 Blueprint 部署该仓库，审阅免费方案与命令后创建服务。若账号或区域不支持免费方案，先确认费用再改用付费方案。
4. 只有服务返回真实的 HTTPS 地址后才能向用户提供网址；验证网页、视频范围请求、单版下载和完整 ZIP 下载。GET `/healthz` 应返回 `{"ready":true}`。

免费实例可能休眠，首次打开可能需要等待唤醒。具体可用性和费用以创建服务时 Render 展示的内容为准。

## 本机验证部署配置

```sh
cd /workspace/-
python3 -m unittest discover -s tests -v
PORT=8081 python3 server.py --host 0.0.0.0 --port 8081 --data-dir review-assets
```

Render 连接器是否能使用，以当前聊天实际提供的工具为准。ChatGPT 中安装应用不保证既有会话即时获得该应用的操作工具；如果没有工具，不能声称已经部署。
