# MiniBrowser（迷你浏览器）

Windows 上的超轻量 WebView2 小窗口浏览器。适合挂本地页面、微信文件传输助手等场景：可置顶、可无边框、可缩放，刷新时尽量绕过缓存。

## 功能

- Edge WebView2 内核（`pywebview`）
- 菜单：地址 / 刷新 / 置顶 / 放大 / 缩小 / 帮助
- 鼠标移入显示标题栏与菜单，移出自动隐藏
- `-n` 模式：始终无边框 + 默认置顶
- 强制刷新：清理 Cache Storage / Service Worker，并对 HTML/JS/CSS 等加时间戳
- 启动时清理本地 WebView2 磁盘缓存（保留 Cookie）
- 单实例：同一时间只允许一个进程，避免用户数据目录冲突
- 支持文件下载（默认开启）

## 下载

到 [Releases](https://github.com/SeamusX9/minibrowser/releases) 下载 `MiniBrowser.exe`。

系统需已安装 [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)。多数 Win10/Win11 已自带。

## 使用

```text
MiniBrowser.exe
MiniBrowser.exe -a "http://127.0.0.1:3123"
MiniBrowser.exe -a "http://127.0.0.1:3123" -n -s 444x223 -z 80
```

| 参数 | 说明 |
|------|------|
| `-a URL` | 启动时打开的网址 |
| `-n` | 隐藏标题栏和菜单栏，并默认置顶 |
| `-s WxH` | 窗口大小，如 `444x223` |
| `-z N` | 页面缩放百分比，如 `80` |

默认首页：微信文件传输助手。

本地页面更新后仍看到旧界面时，点菜单「刷新」。该操作会清站点缓存并重新拉取静态资源。

## 源码运行

要求：Python 3.10+（推荐 3.11/3.12），Windows。

```powershell
pip install -r requirements.txt
python main.py -a "http://127.0.0.1:3123"
```

## 打包 exe

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

产物：`dist\MiniBrowser.exe`

## 目录结构

```text
main.py           # 核心逻辑
build.ps1         # PyInstaller 一键打包
make_icon.py      # 生成默认图标（已有 sea.ico 则跳过）
requirements.txt
sea.ico
```

## 说明

- 用户数据目录：`%APPDATA%\MiniBrowser\webview`
- 刷新刻意避免同步等待 WebView2 异步 API，以免 UI 卡死
- 若页面本身做了强缓存或离线包，仍以服务端/前端策略为准；本工具会尽量绕过浏览器侧缓存

## License

MIT
