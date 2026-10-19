# Render 当前发布：美区 OBD 安装教程

复用现有服务 https://bilingual-video-review.onrender.com ，无需创建新服务。服务名保留历史名称，当前页面与导出仅包含英语 OBD 安装视频。

启动命令：`python server.py --host 0.0.0.0 --port "$PORT" --data-dir review-assets`。
构建命令：`python -m unittest discover -s tests -v`。
健康检查路径：`/healthz`，验证 en.mp4 和 en.srt 均存在。

推送 main 后，如果没有自动部署，在 Render 选择 Manual Deploy → Deploy latest commit。只有新部署 Live 后，线上内容才完成更新。免费实例可能休眠，初次请求需要等待。

当前视频保留用户原片色调与音轨，没有叠加曝光修正或滤镜。历史泰语资产保留，但不进入当前页面或英语下载包。
