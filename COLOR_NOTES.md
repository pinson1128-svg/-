> 历史记录：此文件仅适用于上一条车内收纳托盘视频。当前 OBD 安装教程保留原片色调，没有应用以下曝光与滤镜参数。

# 曝光修正版

本次两版成片从原始 iPhone HLG 素材重新处理，没有直接压暗已经丢失层次的旧 MP4。

- 在线性光下先降低 1.25 EV，再使用 Hable 色调映射转换到 SDR BT.709。
- 泰语版：对比度 1.015、亮度偏移 0、饱和度 1.025，仅保留轻微暖色。
- 英语版：对比度 1.025、亮度偏移 0、饱和度 0.98，轻度锐化。
- 剪辑时间轴、转场、字幕和伴奏保持原版本。
- 视频响应增加 `Cache-Control: no-store`，减少网站更新后继续显示旧成片的问题。

当前环境的重现命令：

```sh
ffmpeg -nostdin -v error -y -i SOURCE.MOV -map 0:v:0 -an \
  -vf 'zscale=t=linear:npl=100,format=gbrpf32le,exposure=exposure=-1.25,zscale=p=bt709,tonemap=tonemap=hable:desat=1,zscale=t=bt709:m=bt709:r=tv,scale=720:1280,setsar=1,fps=30,format=yuv420p' \
  -c:v libx264 -preset fast -crf 18 -threads 2 -map_metadata -1 \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  /workspace/media-workflow/actual/work/normalized.mp4
python3 /workspace/media-workflow/actual/render_samples.py
```

完整渲染器和原始素材保留在云工作区；新素材的原始 HDR 曝光若有差异，不能机械套用同一曝光参数。
