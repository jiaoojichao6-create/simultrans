# Windows 编译环境搭建指南

把以下内容发给你电脑上的 AI，让它帮你装环境：

---

## 第一步：安装 Python 3.11

1. 下载 Python 3.11：https://www.python.org/downloads/release/python-3119/
   - 选 `Windows installer (64-bit)` → `python-3.11.9-amd64.exe`
2. 双击安装，**务必勾选** ☑️ `Add Python to PATH`
3. 安装完成后，打开命令提示符（Win+R → 输入cmd），验证：
   ```
   python --version
   ```
   应该显示 `Python 3.11.9`

## 第二步：下载源码

打开命令提示符，执行：

```
cd C:\
git clone https://github.com/jiaoojichao6-create/simultrans.git
cd simultrans
```

如果没有 git，去 https://git-scm.com/download/win 下载安装

## 第三步：安装依赖

在 `C:\simultrans` 目录下执行：

```
pip install -r requirements.txt
```

如果某个包下载慢，可以加国内镜像：

```
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 第四步：运行

```
python main.py
```

首次运行会自动下载 Whisper 语音识别模型（~75MB），等一会就好。

默认密码：jiaojichao

## 第五步：打包成 exe（可选）

```
pip install pyinstaller
pyinstaller --onefile --windowed --name "Simultrans" --add-data "*.py;." main.py
```

编译完成后 exe 在 `dist/Simultrans.exe`

---

## 依赖清单（共 10 个包）

```
PyQt5          → GUI界面
sounddevice    → 音频采集/播放
numpy          → 音频数据处理
torch          → 深度学习框架（Whisper/VAD用）
torchaudio     → 音频处理
faster-whisper → 语音识别（本地Whisper）
edge-tts       → 语音合成（免费）
requests       → API调用
soundfile      → 音频文件读写
PyMuPDF        → PDF文档解析（术语库导入）
python-docx    → Word文档解析（术语库导入）
```

全部加起来大概下载 500MB（主要是 torch 大），装完后源码目录约 80MB。
