# Bilibili Video Integration Tool

Language: [中文](#中文) | [English](#english)

---

## 中文

[English](#english)

### 项目简介

这是一个用于处理 Bilibili 客户端离线下载缓存的 Python 工具。它只读取本地文件，不联网补 BV，也不调用 Bilibili API；主要功能是扫描 PC/安卓端下载目录，将视频流和音频流合成为 mp4，并按本地可确认的合集信息整理输出。

### 功能

- 支持 PC 端 `.videoInfo` 下载结构。
- 支持安卓端 `entry.json` / `video.m4s` / `audio.m4s` 下载结构。
- 自动处理 PC 端 9 字节混淆头。
- GUI 树形展示合集和单视频。
- 选择合集行时，默认处理合集下全部视频。
- 支持搜索标题、视频号、合集名和路径。
- 支持可见区域缩略图加载，避免滚动到后面时还在优先加载上方缩略图。
- 没有 BV 时显示并导出 `AV{avid}`，不联网补 BV。
- 安卓端合集导出到项目目录下的 `D_bilibili/<合集名>/`，单视频导出到 `D_bilibili/`。
- PC 端合集导出到项目目录下的 `win_bilibili/<合集名>/`，单视频导出到 `win_bilibili/`。

### 环境要求

- Python 3.8+
- ffmpeg / ffprobe
- Tkinter
- Pillow，可选，用于 GUI 缩略图

安装 Pillow：

```powershell
pip install pillow
```

确认 ffmpeg 可用：

```powershell
ffmpeg -version
ffprobe -version
```

### 使用 GUI

```powershell
python gui.py
```

使用步骤：

1. 点击“浏览”选择 Bilibili 下载目录。
2. 点击“扫描”。
3. 在列表中选择单视频或合集文件夹。
4. 点击“开始处理”。

合集文件夹被选中时，会默认处理该合集下全部子视频。

### 使用命令行

```powershell
python run.py
```

然后输入 Bilibili 下载目录，例如：

```text
E:\哔哩哔哩视频合成\download
```

### 输出目录

输出目录固定在项目目录下，不跟随启动命令所在目录变化。

安卓端输出：

```text
E:\Claude_Project\D_bilibili/
├── 合集名称/
│   ├── 子视频标题_AVxxxx.mp4
│   └── 子视频标题_BVyyyy.mp4
└── 单视频标题_AVzzzz.mp4
```

PC 端输出：

```text
E:\Claude_Project\win_bilibili/
├── 合集名称/
│   └── 子视频标题_BVxxxx.mp4
└── 单视频标题_BVyyyy.mp4
```

### 当前合集识别规则

工具只使用本地明确字段，以及由明确合集种子推导出的同作者系列规则，避免凭松散标题标签随意创造合集。

识别优先级：

1. PC 端 `.videoInfo.groupTitle`。
2. 老安卓缓存：`page_data.download_subtitle` 以 `page_data.part` 结尾时，合集名取去掉末尾 `part` 后的文本。
3. 明确多 P：同一目录下有多个 `c_` 子目录，使用 `entry.json.title` 作为合集名。
4. 新安卓缓存：`page_data.part` 包含 `|` 或 `｜` 时，分隔符后文本作为合集名。
5. 二阶段补全：先从明确合集名中提取强系列 token，例如 `stm32`、`armv8`；再只在同一 `owner_id` 或 `owner_name` 下补齐标题或 `part` 含同一 token 的未归类视频。
6. 如果同作者同 token 对应多个不同合集名，则视为歧义，不自动补全。
7. 其他情况不识别为合集。

不会自动识别的情况：

- 只因为视频号是 `AV`。
- 只因为标题有 `【前缀】`。
- 只因为多个视频属于同一作者，且没有明确合集种子。
- 只靠语义聚类，例如 `BootLoader / OTA / 固件` 自动归为 `BootLoader相关`。

### 项目结构

```text
.
├── gui.py                 # Tkinter GUI
├── run.py                 # CLI entry
├── File_processing.py     # scanning, metadata parsing, duration, thumbnails
├── Filepr.py              # ffmpeg merge layer
├── codexproject.md        # current architecture and maintenance notes
├── README.md              # bilingual README
└── image.png              # sample image
```

### 验证

```powershell
python -m py_compile File_processing.py Filepr.py gui.py run.py
```

---

## English

[中文](#中文)

### Overview

This is a Python tool for processing offline Bilibili download caches. It reads local files only. It does not query the Bilibili API, and it does not use the network to convert AV IDs to BV IDs. Its main job is to scan PC/Android download folders, merge video and audio streams into mp4 files, and place confirmed collection items into collection folders.

### Features

- Supports PC download metadata via `.videoInfo`.
- Supports Android download metadata via `entry.json`, `video.m4s`, and `audio.m4s`.
- Handles the 9-byte obfuscation header used by some PC downloads.
- GUI tree view for collections and single videos.
- Selecting a collection row processes all videos under that collection.
- Search by title, video ID, collection name, and path.
- Loads thumbnails for visible rows first, so fast scrolling does not wait for off-screen rows.
- Displays and exports `AV{avid}` when `bvid` is missing. No online lookup is performed.
- Exports Android collection videos to `D_bilibili/<collection name>/` under the project directory, and single videos to `D_bilibili/`.
- Exports PC collection videos to `win_bilibili/<collection name>/` under the project directory, and single videos to `win_bilibili/`.

### Requirements

- Python 3.8+
- ffmpeg / ffprobe
- Tkinter
- Pillow, optional, for GUI thumbnails

Install Pillow:

```powershell
pip install pillow
```

Check ffmpeg:

```powershell
ffmpeg -version
ffprobe -version
```

### GUI Usage

```powershell
python gui.py
```

Steps:

1. Click Browse and select the Bilibili download folder.
2. Click Scan.
3. Select a single video or a collection folder.
4. Click Start Processing.

When a collection folder is selected, all child videos in that collection are processed.

### CLI Usage

```powershell
python run.py
```

Then enter the Bilibili download directory, for example:

```text
E:\哔哩哔哩视频合成\download
```

### Output

Output folders are fixed under the project directory. They do not depend on the shell's current working directory.

Android output:

```text
E:\Claude_Project\D_bilibili/
├── Collection Name/
│   ├── Episode Title_AVxxxx.mp4
│   └── Episode Title_BVyyyy.mp4
└── Single Video Title_AVzzzz.mp4
```

PC output:

```text
E:\Claude_Project\win_bilibili/
├── Collection Name/
│   └── Episode Title_BVxxxx.mp4
└── Single Video Title_BVyyyy.mp4
```

### Current Collection Detection Rules

The tool only uses explicit local metadata, plus same-uploader series completion derived from explicit collection seeds. It avoids creating collections from loose title tags.

Detection priority:

1. PC `.videoInfo.groupTitle`.
2. Old Android cache: when `page_data.download_subtitle` ends with `page_data.part`, the collection name is the remaining prefix.
3. Explicit multi-part structure: multiple `c_` directories under the same video directory, using `entry.json.title` as the collection name.
4. New Android cache: when `page_data.part` contains `|` or `｜`, the text after the separator is the collection name.
5. Two-pass completion: extract strong series tokens such as `stm32` or `armv8` from already confirmed collection names, then complete only ungrouped videos from the same `owner_id` or `owner_name` whose title or `part` contains the same token.
6. If the same uploader and token point to multiple collection names, the rule is considered ambiguous and no automatic completion is applied.
7. Otherwise, the item is treated as a single video.

The tool does not infer collections from:

- AV IDs alone.
- Title prefixes such as `【tag】`.
- Same uploader alone, without an explicit collection seed.
- Semantic clustering, such as grouping `BootLoader / OTA / firmware` into `BootLoader related`.

### Project Layout

```text
.
├── gui.py                 # Tkinter GUI
├── run.py                 # CLI entry
├── File_processing.py     # scanning, metadata parsing, duration, thumbnails
├── Filepr.py              # ffmpeg merge layer
├── codexproject.md        # current architecture and maintenance notes
├── README.md              # bilingual README
└── image.png              # sample image
```

### Verification

```powershell
python -m py_compile File_processing.py Filepr.py gui.py run.py
```
