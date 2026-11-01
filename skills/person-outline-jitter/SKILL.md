---
name: person-outline-jitter
description: 在人物视频轮廓外添加跟随动作的白色圆头虚线，并让线条轻微手绘抖动。适用于人物动态描边、手绘轮廓、抖动虚线；默认不做沿轮廓流动或猫耳装饰。
---

# 人物手绘抖动描边

输入人物视频，输出保留原视频内容、原声音的 MP4。默认效果是人物轮廓外有间距的白色圆头虚线，线条以约 8 Hz 轻微重绘，不是虚线沿轮廓跑动。按每帧人物遮罩描边，不能拿首帧静态轮廓覆盖整段视频。

## 使用

使用本 Skill 目录下 `scripts/render.py`。依赖 Python 3.9+、numpy、opencv-python-headless、ffmpeg/ffprobe；自动人物分割还需要 macOS 的 Vision 和 Swift。先检测现有运行环境，缺少时在工作目录创建 venv 安装依赖，不改系统 Python。

```bash
python -m venv /absolute/work/outline-venv
/absolute/work/outline-venv/bin/python -m pip install numpy opencv-python-headless
/absolute/work/outline-venv/bin/python /absolute/path/person-outline-jitter/scripts/render.py \
  --video /absolute/input.mp4 --output /absolute/new-output-directory
```

输出目录必须是新目录。输出含 `preview.mp4`、`contact-sheet.jpg`、`report.json`、归一化源视频和逐帧遮罩。默认保留分辨率和平均帧率，VFR 转 CFR，音频保留但首次归一化会重编码为 AAC。奇数尺寸最多补 1 像素，不裁剪内容。

可选 `--start`、`--duration` 制作选段；长视频可先做短预览，但明确说明选段范围。默认线宽 12、间距 16、抖动 2.4，单位是短边 1080 的相对像素；可通过 `--stroke`、`--offset`、`--jitter` 调整。`--width` 仅在预览降分辨率或用户要求时使用。

## 轮廓与主体边界

- 内置 Vision 只做人像分割。参考图里的动物可以作为描边样式参考，不能因此宣称自动动物分割已支持。
- 默认适合单一主要人物，取最大连通人物区域；不具备多人身份锁定。多人交叉、被遮挡的身体、分离的手部可能需要修正遮罩。若用户要求指定人物，先明确目标并准备该人物的逐帧遮罩，不能把最大区域选择说成目标追踪。
- 可使用 `--mask-dir` 提供修正后的白主体黑背景 PNG 遮罩；必须对应归一化源视频，尺寸相同、帧数相同，从 `000000.png` 连续编号。非 macOS 可沿用此入口。
- 外轮廓留出间距，圆头虚线，轻微形变，人物上不盖白线。遇到人物丢失隐藏描边，不沿用上一帧的幽灵轮廓。人物被画面裁切时不画封口边框。
- HDR 输入先明确转换为 SDR 并检查颜色，脚本会拒绝直接处理 HDR。不能默默降低色彩质量。
- 不默认添加耳朵、箭头、字幕、音乐、发光或背景变化；参考截图只能确定静态样式，动态方式以用户描述为准。

## 验证与交付

运行后查看报告中的缺失帧、多连通区域标记；抽查首、中、尾和快速动作/遮挡帧，并看实际播放，确认描边跟人走、虚线没有全圈滑动、抖动轻微且不盖住脸和身体。标记不是质量结论：需要目视判断，检查失败后修正遮罩或明确说明局限。

核对输出尺寸、帧数、时长和音轨；脚本会核对帧数和音轨是否存在。展示本地 MP4 和必要的静帧，报告实测范围。创建 Skill、脚本验证、素材测试、用户审美验收分别说明。没有用户的视频时不要声称已在用户素材上通过。
