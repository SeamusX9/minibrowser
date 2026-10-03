"""迷你浏览器：Windows WebView2 内核。

启动参数：
  -a URL   打开指定网址
  -n       隐藏标题/菜单栏，并默认置顶
  -s WxH   窗口大小，如 444x223
  -z N     页面缩放百分比，如 80
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import sys
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import webview
from webview.menu import MenuAction

DEFAULT_URL = "https://filehelper.weixin.qq.com/"
DEFAULT_WIDTH = 400
DEFAULT_HEIGHT = 400
DEFAULT_ZOOM = 100
TITLE = "迷你浏览器"
INSTANCE_PORT = 58472
STORAGE = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "MiniBrowser", "webview"
)
STATIC_EXTS = {
    ".css", ".gif", ".htm", ".html", ".ico", ".jpeg", ".jpg", ".js", ".json",
    ".map", ".mjs", ".png", ".svg", ".ttf", ".wasm", ".webp", ".woff", ".woff2",
}
CACHE_DIRS = {
    "Cache", "Code Cache", "DawnCache", "GPUCache", "GrShaderCache",
    "Service Worker", "ShaderCache",
}
HELP = """启动参数（对 MiniBrowser.exe 同样有效）

-a URL     启动打开网址，如 -a "http://127.0.0.1:3123"
-n         始终隐藏标题栏/菜单栏，并默认置顶
-s 宽x高   窗口大小，如 -s 444x223
-z 百分比  页面缩放，如 -z 80

示例：
  MiniBrowser.exe -a "http://127.0.0.1:3123" -n -s 444x223 -z 80
"""

webview.settings["ALLOW_DOWNLOADS"] = True
_instance_sock: socket.socket | None = None
_timers: list = []


def resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=TITLE)
    p.add_argument("-a", dest="url", default=None, help="启动网址")
    p.add_argument("-n", dest="no_chrome", action="store_true", help="无边框并置顶")
    p.add_argument("-s", dest="size", default=None, help="窗口大小 WxH")
    p.add_argument("-z", dest="zoom", default=None, help="缩放百分比")
    args, _ = p.parse_known_args(argv)

    width, height = DEFAULT_WIDTH, DEFAULT_HEIGHT
    if args.size:
        m = re.fullmatch(r"(\d+)\s*[xX×]\s*(\d+)", args.size.strip())
        if m:
            width, height = max(1, int(m.group(1))), max(1, int(m.group(2)))

    zoom = DEFAULT_ZOOM
    if args.zoom is not None:
        try:
            zoom = int(str(args.zoom).strip().rstrip("%"))
        except ValueError:
            zoom = DEFAULT_ZOOM
        zoom = max(30, min(300, zoom))

    url = (args.url or "").strip() or DEFAULT_URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    args.url, args.width, args.height = url, width, height
    args.zoom_factor = round(zoom / 100.0, 2)
    return args


def ensure_single_instance() -> None:
    global _instance_sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", INSTANCE_PORT))
        sock.listen(1)
    except OSError:
        sock.close()
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.MessageBoxW(
                    0, "迷你浏览器已在运行。\n请先关闭已有窗口后再打开。", TITLE, 0x30
                )
            except OSError:
                pass
        sys.exit(0)
    _instance_sock = sock


def on_ui(native, fn, *, async_: bool = False) -> None:
    """在 WinForms UI 线程执行；菜单回调在子线程，必须走这里。"""
    if native is None:
        return
    try:
        if async_:
            from System import Action

            native.BeginInvoke(Action(fn))
            return
        if getattr(native, "InvokeRequired", False):
            from System import Func, Type

            native.Invoke(Func[Type](fn))
        else:
            fn()
    except Exception:
        try:
            fn()
        except Exception:
            pass


def ask_url(initial: str) -> str | None:
    import tkinter as tk
    from tkinter import ttk

    out: dict[str, str | None] = {"url": None}
    root = tk.Tk()
    root.title("修改地址")
    root.attributes("-topmost", True)
    root.resizable(True, False)
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frame, text="请输入网址：").pack(anchor=tk.W)
    entry = ttk.Entry(frame, width=72, font=("Segoe UI", 12))
    entry.pack(fill=tk.X, pady=(8, 16))
    entry.insert(0, initial)
    entry.select_range(0, tk.END)
    entry.focus_set()
    row = ttk.Frame(frame)
    row.pack(fill=tk.X)

    def ok(_e=None) -> None:
        out["url"] = entry.get().strip() or None
        root.destroy()

    def cancel(_e=None) -> None:
        out["url"] = None
        root.destroy()

    ttk.Button(row, text="确定", command=ok).pack(side=tk.RIGHT, padx=(8, 0))
    ttk.Button(row, text="取消", command=cancel).pack(side=tk.RIGHT)
    root.bind("<Return>", ok)
    root.bind("<Escape>", cancel)
    root.update_idletasks()
    w, h = max(root.winfo_reqwidth(), 560), max(root.winfo_reqheight(), 140)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
    root.mainloop()
    return out["url"]


def show_help() -> None:
    import tkinter as tk
    from tkinter import scrolledtext, ttk

    root = tk.Tk()
    root.title("帮助 - 启动参数")
    root.attributes("-topmost", True)
    frame = ttk.Frame(root, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)
    text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, width=72, height=22, font=("Consolas", 11))
    text.pack(fill=tk.BOTH, expand=True)
    text.insert(tk.END, HELP)
    text.configure(state=tk.DISABLED)
    ttk.Button(frame, text="关闭", command=root.destroy).pack(pady=(10, 0))
    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"620x460+{(sw - 620) // 2}+{(sh - 460) // 2}")
    root.mainloop()


def set_icon(hwnd: int) -> None:
    path = resource_path("sea.ico")
    if sys.platform != "win32" or not os.path.isfile(path) or not hwnd:
        return
    try:
        import ctypes

        hicon = ctypes.windll.user32.LoadImageW(None, path, 1, 0, 0, 0x10 | 0x4000)
        if hicon:
            ctypes.windll.user32.SendMessageW(hwnd, 0x80, 0, hicon)
            ctypes.windll.user32.SendMessageW(hwnd, 0x80, 1, hicon)
    except OSError:
        pass


def set_topmost(native, enabled: bool) -> None:
    on_ui(native, lambda: setattr(native, "TopMost", enabled))


def set_zoom(native, factor: float) -> None:
    def apply() -> None:
        ctrl = getattr(native, "webview", None)
        if ctrl is not None:
            ctrl.ZoomFactor = factor

    on_ui(native, apply)


def cache_bust(url: str) -> str:
    parts = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "_mbts"]
    q.append(("_mbts", str(int(time.time() * 1000))))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def maybe_bust_static(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return url
    ext = os.path.splitext(urlsplit(url).path.lower())[1]
    return cache_bust(url) if ext in STATIC_EXTS else url


def purge_disk_cache() -> None:
    if not os.path.isdir(STORAGE):
        return
    for root, _dirs, _files in os.walk(STORAGE, topdown=False):
        if os.path.basename(root) in CACHE_DIRS:
            shutil.rmtree(root, ignore_errors=True)


def enable_fresh_loads() -> None:
    """关闭 HTTP 缓存；静态资源请求去掉协商缓存头并加时间戳。"""
    from webview.platforms.edgechromium import EdgeChrome

    orig_init = EdgeChrome.__init__
    orig_req = EdgeChrome.on_web_resource_request

    def patched_init(self, form, window, cache_dir):
        add = form.Controls.Add

        def add_and_patch(ctrl):
            try:
                props = ctrl.CreationProperties
                args = str(getattr(props, "AdditionalBrowserArguments", "") or "")
                extra = []
                if "--disable-http-cache" not in args:
                    extra.append("--disable-http-cache")
                if "--disk-cache-size=" not in args:
                    extra.append("--disk-cache-size=1")
                if extra:
                    props.AdditionalBrowserArguments = (args + " " + " ".join(extra)).strip()
                    ctrl.CreationProperties = props
            except Exception:
                pass
            return add(ctrl)

        form.Controls.Add = add_and_patch
        try:
            orig_init(self, form, window, cache_dir)
        finally:
            form.Controls.Add = add

    def patched_req(self, sender, args):
        try:
            req, headers = args.Request, args.Request.Headers
            for name in (
                "If-None-Match", "If-Modified-Since", "If-Match",
                "If-Unmodified-Since", "If-Range",
            ):
                try:
                    headers.RemoveHeader(name)
                except Exception:
                    pass
            headers.SetHeader("Cache-Control", "no-cache, no-store, max-age=0")
            headers.SetHeader("Pragma", "no-cache")
            if str(getattr(req, "Method", "GET") or "GET").upper() == "GET":
                uri = str(req.Uri)
                busted = maybe_bust_static(uri)
                if busted != uri:
                    try:
                        req.Uri = busted
                    except Exception:
                        from System import Uri

                        req.Uri = Uri(busted)
        except Exception:
            pass
        return orig_req(self, sender, args)

    EdgeChrome.__init__ = patched_init
    EdgeChrome.on_web_resource_request = patched_req


def hard_refresh_js(target: str) -> str:
    t = json.dumps(target)
    return f"""
    (function(){{
      var target={t};
      function go(){{ location.replace(target); }}
      var tasks=[];
      try{{ if(window.caches) tasks.push(caches.keys().then(function(ks){{
        return Promise.all(ks.map(function(k){{ return caches.delete(k); }}));
      }})); }}catch(e){{}}
      try{{ if(navigator.serviceWorker) tasks.push(navigator.serviceWorker.getRegistrations().then(function(rs){{
        return Promise.all(rs.map(function(r){{ return r.unregister(); }}));
      }})); }}catch(e){{}}
      Promise.all(tasks).then(go, go); return 1;
    }})();
    """


def run_js(native, script: str) -> bool:
    def apply() -> None:
        ctrl = getattr(native, "webview", None)
        if ctrl is None:
            return
        try:
            from System import String

            m = ctrl.GetType().GetMethod("ExecuteScriptAsync", [String]) or ctrl.GetType().GetMethod(
                "ExecuteScriptAsync"
            )
            if m is not None:
                m.Invoke(ctrl, [script])
                return
        except Exception:
            pass
        ctrl.ExecuteScriptAsync(script)

    if native is None:
        return False
    on_ui(native, apply, async_=True)
    return True


def apply_frameless(native) -> None:
    import System.Windows.Forms as WinForms

    style = getattr(WinForms.FormBorderStyle, "None")
    bounds = native.Bounds
    for ctrl in list(native.Controls):
        if isinstance(ctrl, WinForms.MenuStrip):
            ctrl.Visible = False
    native.FormBorderStyle = style
    native.Bounds = bounds


def setup_auto_hide(native) -> None:
    import System.Windows.Forms as WinForms

    menu = next((c for c in native.Controls if isinstance(c, WinForms.MenuStrip)), None)
    bordered = WinForms.FormBorderStyle.Sizable
    frameless = getattr(WinForms.FormBorderStyle, "None")
    visible = {"v": True}

    def busy() -> bool:
        if menu is None:
            return False
        for item in menu.Items:
            dd = getattr(item, "DropDown", None)
            if dd is not None and dd.Visible:
                return True
            if getattr(item, "Pressed", False):
                return True
        return False

    def set_chrome(show: bool) -> None:
        if visible["v"] == show or (not show and busy()):
            return
        visible["v"] = show
        bounds = native.Bounds
        if show:
            native.FormBorderStyle = bordered
            if menu is not None:
                menu.Visible = True
        else:
            if menu is not None:
                menu.Visible = False
            native.FormBorderStyle = frameless
        native.Bounds = bounds

    def poll(_s, _a) -> None:
        try:
            if native.IsDisposed:
                return
            pt, rect = WinForms.Control.MousePosition, native.Bounds
            inside = rect.Left <= pt.X <= rect.Right and rect.Top <= pt.Y <= rect.Bottom
            set_chrome(inside)
        except Exception:
            pass

    timer = WinForms.Timer()
    timer.Interval = 120
    timer.Tick += poll
    timer.Start()
    _timers.append(timer)


def main() -> None:
    args = parse_args()
    ensure_single_instance()
    os.makedirs(STORAGE, exist_ok=True)
    purge_disk_cache()
    enable_fresh_loads()

    pinned = {"on": bool(args.no_chrome)}
    zoom = {"v": float(args.zoom_factor)}

    window = webview.create_window(
        TITLE,
        args.url,
        width=args.width,
        height=args.height,
        resizable=True,
        text_select=True,
        zoomable=True,
    )

    def current_url() -> str:
        try:
            return window.get_current_url() or args.url
        except Exception:
            return args.url

    def change_url() -> None:
        url = ask_url(current_url())
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        window.load_url(url)

    def refresh() -> None:
        target = cache_bust(current_url())
        if run_js(window.native, hard_refresh_js(target)):
            return
        window.load_url(target)

    def toggle_pin() -> None:
        if window.native is None:
            return
        pinned["on"] = not pinned["on"]
        set_topmost(window.native, pinned["on"])

    def zoom_by(delta: float) -> None:
        if window.native is None:
            return
        zoom["v"] = max(0.3, min(3.0, round(zoom["v"] + delta, 2)))
        set_zoom(window.native, zoom["v"])

    menu = None
    if not args.no_chrome:
        menu = [
            MenuAction("地址", change_url),
            MenuAction("刷新", refresh),
            MenuAction("置顶", toggle_pin),
            MenuAction("放大", lambda: zoom_by(0.1)),
            MenuAction("缩小", lambda: zoom_by(-0.1)),
            MenuAction("帮助", show_help),
        ]

    def on_ready() -> None:
        window.events.shown.wait(15)
        native = window.native
        if native is None:
            return
        set_icon(int(native.Handle.ToInt32()))

        def startup() -> None:
            if args.no_chrome:
                apply_frameless(native)
                set_topmost(native, True)
            else:
                setup_auto_hide(native)
            if abs(zoom["v"] - 1.0) > 1e-6:
                set_zoom(native, zoom["v"])

        on_ui(native, startup)

    kwargs = dict(
        func=on_ready,
        gui="edgechromium",
        private_mode=False,
        storage_path=STORAGE,
    )
    if menu is not None:
        kwargs["menu"] = menu
    webview.start(**kwargs)


if __name__ == "__main__":
    main()
