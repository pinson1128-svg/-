# 美区记录仪开箱：预览与导出

当前是最新上传素材的美区英语版，30 秒，静音。只做轻度剪辑和英文动作字幕，保留源视频的色调、滤镜、尺寸及色彩标签。不会使用旧版 OBD 素材或车内收纳视频的调色参数。

画面动作：展示机身、翻转镜头、检查接口、查看 microSD 卡、打开配件层、查看说明书、展示配件及调整机身角度。动作说明只描述画面，不虚构未验证的产品规格或配件性能。

## 运行与验证

```sh
python3 server.py --port 8080 --data-dir review-assets
python3 -m unittest discover -s tests -v
```

Python 标准库即可运行。Render 继续使用现有服务，监听平台注入的 PORT。`/healthz` 检查 en.mp4 和 en.srt；`/api/assets` 返回当前两份文件状态。

- `/media/en-video`：视频预览，支持范围请求。
- `/download/en-video`：英语版 MP4。
- `/download/en-subtitles`：英文动作 SRT。
- `/download/english.zip`：英语视频、字幕和说明。

当前成片没有任何音频轨道，原声已完全移除；不添加配音或背景音乐。旧泰语文件保留，但不在页面展示，不纳入导出包。

## 重现

```sh
python3 tools/render_unboxing.py SOURCE.mp4 --output OUTPUT_DIRECTORY
```

此渲染器针对本次 720×1280、30fps、BT.709 色原色/矩阵、sRGB 传递函数的 SDR 素材。剪辑计划见 CUTS。没有曝光、调色、锐化、色调映射、缩放或变速处理。字幕与拼接需重编码，会有少量压缩差异。

输入文件 2727b8323f7fb3b175314513f0ef8ea2.mp4 保留在云工作区，未将原片上传至 GitHub。导出后验证完整解码、30 秒时长、无音轨、源色彩标签与对应原始帧，再更新 review-assets/en.mp4 和 en.srt。旧 tools/render_obd.py 仅用于上一条 OBD 教程，不用于本条素材。

## Render

网站为 https://bilingual-video-review.onrender.com 。推送 GitHub main 后等待对应提交部署 Live，若未自动更新，在 Render 选择 Manual Deploy → Deploy latest commit。GitHub 推送成功不等同于已完成线上部署。

## ElevenLabs 英语旁白

接入步骤见 [ELEVENLABS_SETUP.md](ELEVENLABS_SETUP.md)。在 Render 环境变量设置 ELEVENLABS_API_KEY 和至少 20 位的 VOICE_ACCESS_TOKEN，重新部署后可在网页选择声音并生成独立配音 MP3。Key 不下发浏览器。网页输入独立口令，不要输入 API Key。生成会使用 ElevenLabs 额度。当前不会自动把 MP3 混入视频或添加配乐。真实账号和额度尚待用户配置后验证；第三方调用使用替身完成自动测试，未消耗真实额度。
