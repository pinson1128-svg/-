# 美区 OBD 安装教程：预览与导出

当前版本只展示用户新上传素材的美区英语版，约 29.7 秒。内容是 OBD 供电线安装、记录仪开机与停车供电检查。原片已经是 SDR BT.709，本次没有使用调色、曝光、饱和度、锐化、色调映射或额外滤镜。字幕与片段拼接需要视频重编码，所以不声称文件逐字节等同原片。

原音轨保留并跟随剪辑，切口使用 15 毫秒音频淡入淡出。没有生成英语人声配音。停车模式需相机、供电线与车辆支持；不承诺未经验证的持续录制时长。

## 启动和部署

```sh
python3 server.py --port 8080 --data-dir review-assets
```

Python 标准库即可运行。Render 保持现有启动命令和域名，无需新建服务。源码推送后，必须等待 Render 完成对应提交的新部署，才会更新线上视频。

`review-assets/en.mp4` 和 `review-assets/en.srt` 是当前导出文件。先前泰语文件保留作历史素材，不展示、不作为就绪依赖，也不进入本次英语导出包。

## 导出接口

- `/media/en-video`：浏览器预览，支持字节范围请求。
- `/download/en-video`：英语 MP4。
- `/download/en-subtitles`：英语 SRT。
- `/download/english.zip`：视频、字幕与说明文件。
- `/api/assets`：当前英语文件状态。
- `/healthz`：两份英语文件就绪后返回 200，否则 503。

旧 `/download/bilingual.zip` 路径保留兼容，返回同一英语包；不会混入旧素材。

## 重现编辑

```sh
python3 tools/render_obd.py /path/to/053e5b8c16c7d3eb6d11f97158716e15.mp4 --output /path/to/output
```

剪辑计划在脚本的 CUTS 列表，输出 en.mp4、en.srt、edit-plan.json。原始素材保留在云环境，未新增发布到 GitHub。更新导出前先检查视频和字幕，再替换 review-assets 下同名文件。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

实际成片还验证了完整解码、时长、尺寸、SDR 色彩标记，并比较字幕区域以外的对应原始帧，确认颜色只有重编码带来的轻微像素差异。
