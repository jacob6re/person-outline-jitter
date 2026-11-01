# person-outline-jitter · 人物手绘动态描边

识别视频里的人物，在轮廓外添加白色圆头虚线，并让线条轻微手绘抖动。描边逐帧跟随人物，默认约每秒 8 次轻微重绘，虚线位置保持在轮廓附近。

## 安装到 AI 编程助手

安装命令需要 Node.js 22.20.0 或更新版本（本次使用 Node.js 24 验证）。

```bash
npx -y skills add jacob6re/person-outline-jitter -g --all
```

安装后，把视频交给助手并说：

> 用 person-outline-jitter 给这段人物视频加上白色手绘抖动虚线描边，保留原声，先给我预览。

## 环境

- Python 3.9+，依赖 `numpy`、`opencv-python-headless`
- `ffmpeg` 和 `ffprobe`
- 自动人物分割需要 macOS、Swift 和系统 Vision 框架
- 其他系统可通过 `--mask-dir` 使用已有逐帧人物遮罩

安装 Skill 会提供指令和脚本；运行视频处理前需要准备上述依赖。

## 直接运行

```bash
git clone https://github.com/jacob6re/person-outline-jitter.git
cd person-outline-jitter
python3 -m venv .venv
.venv/bin/python -m pip install numpy opencv-python-headless
.venv/bin/python skills/person-outline-jitter/scripts/render.py \
  --video /path/to/input.mp4 \
  --output /path/to/new-output
```

输出目录必须尚不存在。结果包含 `preview.mp4`、抽帧检查图 `contact-sheet.jpg`、检测报告 `report.json`、归一化源视频和逐帧遮罩。

默认保留原始分辨率、平均帧率和原声音内容；可变帧率视频转为恒定帧率，音频归一化为 AAC。视频处理在本地执行。

## 调整效果

```bash
.venv/bin/python skills/person-outline-jitter/scripts/render.py \
  --video /path/to/input.mp4 \
  --output /path/to/another-new-output \
  --stroke 12 --offset 16 --jitter 2.4
```

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `--stroke` | 12 | 描边线宽 |
| `--offset` | 16 | 人物与描边的间距 |
| `--jitter` | 2.4 | 轻微抖动幅度；设为 0 可去除位置抖动 |
| `--start` | 0 | 从第几秒开始 |
| `--duration` | 全段 | 处理时长，单位秒 |
| `--width` | 原宽度 | 可选输出宽度，等比例缩放 |
| `--mask-dir` | 自动生成 | 自备逐帧人物遮罩目录 |

线宽、间距和抖动幅度以短边 1080 像素为基准，按视频尺寸缩放。自备遮罩必须与归一化视频逐帧对应、尺寸一致，并从 `000000.png` 连续编号，白色表示人物、黑色表示背景。

## 适用范围与验证

默认适合单一主要人物，选取人物遮罩中的最大连通区域。多人交叉、分离的手部、严重遮挡和复杂边缘可能需要修正遮罩；当前不提供指定人物的身份锁定，也不支持自动动物分割。HDR 视频需要先转换为 SDR。

已在一段 720×960、30 fps、188 帧的真实人物视频上生成完整预览，并检查输出帧数、尺寸、音轨及代表帧；另检查了描边在人物外、随轮廓移动、轻微形变以及人物消失时隐藏的行为。不同素材仍需检查实际输出。
