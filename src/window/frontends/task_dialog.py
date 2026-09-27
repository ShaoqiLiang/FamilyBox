"""TaskDialogIndirect 包装:原生对话框 + 自定义按钮文字(如 [复制][确定])。

零依赖 ctypes 实现。TaskDialog 必须**在 comctl32 v6 激活上下文内**调用:
本模块首次使用前会写临时 manifest 并 ActivateActCtx(见 _ensure_comctl32_v6),
否则 Win11 24H2 实测返回 E_INVALIDARG(0x80070057)。调用失败返回 -1,
由调用方回退 _message_box。调用路径带 [TD] 打印便于排查。
"""

from __future__ import annotations

import ctypes
import sys
import tempfile
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable

if sys.platform != "win32":  # pragma: no cover - 平台守卫
    raise ImportError("task_dialog is Windows-only")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

TDF_USE_HICON_MAIN = 0x2
TDF_ALLOW_DIALOG_CANCELLATION = 0x8
# 注意:TDF_POSITION_RELATIVE_TO_WINDOW(0x400) 在 Win11 24H2 上会使对话框
# 底部多出一条空白灰带(2026-09-20 实测),已弃用——对话框默认屏幕居中。
TD_ERROR_ICON = -2  # MAKEINTRESOURCEW(-2),commctrl.h 定义
TDN_BUTTON_CLICKED = 2  # TaskDialog 回调消息:wp = 被点按钮 ID
TDM_SET_BUTTON_TEXT = 0x472  # WM_USER + 114
TDM_CLICK_BUTTON = 0x466  # WM_USER + 102
TDM_SET_PROGRESS_BAR_RANGE = 0x469  # WM_USER + 105
TDM_SET_PROGRESS_BAR_POS = 0x46A  # WM_USER + 106
TDF_SHOW_PROGRESS_BAR = 0x200
TDN_CREATED = 0  # TaskDialog 回调消息:对话框构造完成
IDCANCEL = 2
S_OK, S_FALSE = 0, 1  # 回调返回 S_FALSE = 阻止对话框关闭

_MANIFEST = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <dependency>
    <dependentAssembly>
      <assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls"
                        version="6.0.0.0" processorArchitecture="*"
                        publicKeyToken="6595b64144ccf1df" language="*"/>
    </dependentAssembly>
  </dependency>
</assembly>
"""


PFTASKDIALOGCALLBACK = ctypes.WINFUNCTYPE(
    ctypes.c_long,  # HRESULT
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
    wintypes.LPARAM,  # lpRefData
)


class TASKDIALOG_BUTTON(ctypes.Structure):
    _pack_ = 4
    _fields_ = [("nButtonID", ctypes.c_int), ("pszButtonText", wintypes.LPCWSTR)]


class _U1(ctypes.Union):
    _pack_ = 4
    _fields_ = [("hMainIcon", wintypes.HICON), ("pszMainIcon", wintypes.LPCWSTR)]


class _U2(ctypes.Union):
    _pack_ = 4
    _fields_ = [("hFooterIcon", wintypes.HICON), ("pszFooterIcon", wintypes.LPCWSTR)]


class TASKDIALOGCONFIG(ctypes.Structure):
    """MinGW commctrl.h 同款 **4 字节打包布局(sizeof=160)**。

    Win11 24H2 (26100) comctl32 v6.10 实测:cbSize=160 通过校验;自然对齐的
    176 会被 E_INVALIDARG 拒绝(2026-09-19 诊断记录,勿改回自然对齐)。
    """

    _pack_ = 4
    _anonymous_ = ("u1", "u2")
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("hwndParent", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("dwFlags", wintypes.DWORD),
        ("dwCommonButtons", wintypes.DWORD),
        ("pszWindowTitle", wintypes.LPCWSTR),
        ("u1", _U1),
        ("pszMainInstruction", wintypes.LPCWSTR),
        ("pszContent", wintypes.LPCWSTR),
        ("cButtons", wintypes.UINT),
        ("pButtons", ctypes.POINTER(TASKDIALOG_BUTTON)),
        ("nDefaultButton", ctypes.c_int),
        ("cRadioButtons", wintypes.UINT),
        ("pRadioButtons", ctypes.POINTER(TASKDIALOG_BUTTON)),
        ("nDefaultRadioButton", ctypes.c_int),
        ("pszVerificationText", wintypes.LPCWSTR),
        ("pszExpandedInformation", wintypes.LPCWSTR),
        ("pszExpandedControlText", wintypes.LPCWSTR),
        ("pszCollapsedControlText", wintypes.LPCWSTR),
        ("u2", _U2),
        ("pszFooter", wintypes.LPCWSTR),
        ("pfCallback", PFTASKDIALOGCALLBACK),
        ("lpCallbackData", ctypes.c_longlong),  # LONG_PTR
        ("cxWidth", wintypes.UINT),
    ]


class ACTCTX(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.ULONG),
        ("dwFlags", wintypes.DWORD),
        ("lpSource", wintypes.LPCWSTR),
        ("wProcessorArchitecture", wintypes.USHORT),
        ("wLangId", wintypes.USHORT),
        ("lpAssemblyDirectory", wintypes.LPCWSTR),
        ("lpResourceName", wintypes.LPCWSTR),
        ("lpApplicationName", wintypes.LPCWSTR),
    ]


user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
kernel32.CreateActCtxW.restype = wintypes.HANDLE
kernel32.CreateActCtxW.argtypes = (ctypes.POINTER(ACTCTX),)
kernel32.ActivateActCtx.restype = wintypes.BOOL
kernel32.ActivateActCtx.argtypes = (wintypes.HANDLE, ctypes.POINTER(ctypes.c_ulonglong))
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)

_ACTIVATED = False
comctl32 = None  # type: ignore[assignment]


def _ensure_comctl32_v6(debug: bool) -> None:
    """激活 comctl32 v6 激活上下文并绑定 comctl32(仅首次;必须先于其加载)。"""
    global _ACTIVATED, comctl32
    if _ACTIVATED:
        return
    try:
        mpath = Path(tempfile.gettempdir()) / "FamilyBox_common_controls_v6.manifest"
        if not mpath.exists():
            mpath.write_text(_MANIFEST, encoding="utf-8")
        actx = ACTCTX()
        actx.cbSize = ctypes.sizeof(ACTCTX)
        actx.lpSource = str(mpath)
        h = kernel32.CreateActCtxW(ctypes.byref(actx))
        invalid = ctypes.c_void_p(-1).value
        if h not in (None, 0) and h != invalid:
            cookie = ctypes.c_ulonglong(0)
            kernel32.ActivateActCtx(h, ctypes.byref(cookie))
            if debug:
                print("[TD] comctl32 v6 activation context ON", flush=True)
        elif debug:
            print("[TD] CreateActCtxW failed — TaskDialog 将不可用", flush=True)
    except Exception as e:  # 激活失败不阻断,调用时再降级
        if debug:
            print(f"[TD] activation error: {e}", flush=True)
    comctl32 = ctypes.windll.comctl32
    comctl32.TaskDialogIndirect.restype = wintypes.HRESULT
    comctl32.TaskDialogIndirect.argtypes = (
        ctypes.POINTER(TASKDIALOGCONFIG),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(wintypes.BOOL),
    )
    _ACTIVATED = True


def show_task_dialog(
    owner: int,
    title: str,
    main_instruction: str,
    content: str,
    buttons: list[tuple[int, str]],
    default_button_id: int,
    error_icon: bool = False,
    copy_button_id: int | None = None,
    debug: bool = False,
) -> int:
    """模态原生对话框;返回被点击的按钮 ID,调用失败返回 -1。

    main_instruction:大字加粗主指令——**不可为 NULL**(Win11 24H2 实测:
    NULL 时 API 返回 E_INVALIDARG);无内容时传空串。
    debug=True 时打印 [TD] 调试信息(release 保持静默)。
    """
    _ensure_comctl32_v6(debug)
    cc = comctl32
    assert cc is not None
    config = TASKDIALOGCONFIG()
    config.cbSize = ctypes.sizeof(TASKDIALOGCONFIG)
    config.hwndParent = wintypes.HWND(owner) if owner else None
    config.dwFlags = TDF_ALLOW_DIALOG_CANCELLATION
    config.pszWindowTitle = title
    config.pszMainInstruction = main_instruction
    config.pszContent = content
    arr = (TASKDIALOG_BUTTON * len(buttons))()
    for i, (bid, text) in enumerate(buttons):
        arr[i].nButtonID = bid
        arr[i].pszButtonText = text
    config.cButtons = len(buttons)
    config.pButtons = arr
    config.nDefaultButton = default_button_id
    if error_icon:
        # 原版 MessageBox 的红 X:系统共享 HICON + TDF_USE_HICON_MAIN
        # (packed 布局下 MAKEINTRESOURCE 资源字符串指针会引发解引用崩溃,勿用)
        config.dwFlags |= 0x2  # TDF_USE_HICON_MAIN
        config.u1.hMainIcon = user32.LoadIconW(
            None, wintypes.LPCWSTR(32510)
        )  # IDI_HAND

    # 回调:点 [复制] → 写剪贴板 + 按钮文字改「已复制」,返回 S_FALSE 保持打开;
    # 其他按钮返回 S_OK 正常关闭
    copy_full = f"{main_instruction}\n{content}" if main_instruction else content

    def _taskdialog_callback(hwnd: int, msg: int, wp: int, lp: int, ref: int) -> int:
        if (
            msg == TDN_BUTTON_CLICKED
            and copy_button_id is not None
            and wp == copy_button_id
        ):
            copy_to_clipboard(hwnd, copy_full, debug)
            if hwnd:
                tip = ctypes.create_unicode_buffer("已复制")
                user32.SendMessageW(
                    hwnd,
                    TDM_SET_BUTTON_TEXT,
                    copy_button_id,
                    ctypes.addressof(tip),
                )
            return S_FALSE
        return S_OK

    cbref = PFTASKDIALOGCALLBACK(_taskdialog_callback)  # 模态期间保活
    config.pfCallback = cbref

    if debug:
        print(
            f"[TD] call: cbSize={config.cbSize} owner={owner} flags=0x{config.dwFlags:x} "
            f"instr={main_instruction!r} content_len={len(content)} "
            f"nbuttons={len(buttons)} default={default_button_id} icon={error_icon}",
            flush=True,
        )
    pn = ctypes.c_int(-1)
    hr = cc.TaskDialogIndirect(ctypes.byref(config), ctypes.byref(pn), None, None)
    if debug:
        print(
            f"[TD] result: hr=0x{hr & 0xFFFFFFFF:08X} clicked={pn.value} "
            f"lasterr={kernel32.GetLastError()}",
            flush=True,
        )
    return pn.value if hr == 0 else -1


def show_progress_dialog(
    owner: int,
    title: str,
    heading: str,
    work: Callable[[Callable[[int], None]], Any],
    cancel_text: str = "取消",
    debug: bool = False,
) -> tuple[int, Any]:
    """模态进度对话框：work(progress) 在后台线程执行，进度条 0-100。

    work 接收 progress(pct: int)（0-100，跨线程 PostMessage 进度条），
    其返回值原样带回。完成/异常后自动点「取消」ID 关闭对话框：
    返回 (被点按钮 ID, work 结果)。用户提前取消或 work 抛异常时结果为 None
    （work 会在后台跑完，结果被丢弃）。
    """
    _ensure_comctl32_v6(debug)
    cc = comctl32
    assert cc is not None
    holder: dict[str, Any] = {"report": None}
    config = TASKDIALOGCONFIG()
    config.cbSize = ctypes.sizeof(TASKDIALOGCONFIG)
    config.hwndParent = wintypes.HWND(owner) if owner else None
    config.dwFlags = TDF_ALLOW_DIALOG_CANCELLATION | TDF_SHOW_PROGRESS_BAR
    config.pszWindowTitle = title
    config.pszMainInstruction = heading
    config.pszContent = ""
    arr = (TASKDIALOG_BUTTON * 1)()
    arr[0].nButtonID = IDCANCEL
    arr[0].pszButtonText = cancel_text
    config.cButtons = 1
    config.pButtons = arr
    config.nDefaultButton = IDCANCEL

    def _taskdialog_callback(hwnd: int, msg: int, wp: int, lp: int, ref: int) -> int:
        if msg != TDN_CREATED or not hwnd:
            return S_OK
        # 范围 0-100：MAKELPARAM(min, max) = (max << 16) | min
        user32.SendMessageW(hwnd, TDM_SET_PROGRESS_BAR_RANGE, 0, (100 << 16))

        def worker() -> None:
            try:
                holder["report"] = work(
                    lambda pct: user32.PostMessageW(
                        hwnd, TDM_SET_PROGRESS_BAR_POS, max(0, min(100, int(pct))), 0
                    )
                )
            except Exception as e:  # 结果折叠为 None，不阻断关闭
                if debug:
                    print(f"[TD] progress work error: {e}", flush=True)
            finally:
                user32.PostMessageW(hwnd, TDM_CLICK_BUTTON, IDCANCEL, 0)

        threading.Thread(target=worker, daemon=True, name="fb-td-progress").start()
        return S_OK

    cbref = PFTASKDIALOGCALLBACK(_taskdialog_callback)  # 模态期间保活
    config.pfCallback = cbref

    if debug:
        print(f"[TD] progress call: owner={owner} heading={heading!r}", flush=True)
    pn = ctypes.c_int(-1)
    hr = cc.TaskDialogIndirect(ctypes.byref(config), ctypes.byref(pn), None, None)
    if debug:
        print(
            f"[TD] progress result: hr=0x{hr & 0xFFFFFFFF:08X} clicked={pn.value}",
            flush=True,
        )
    return (pn.value if hr == 0 else -1), holder["report"]


def copy_to_clipboard(hwnd: int, text: str, debug: bool = False) -> None:
    """把文本写入剪贴板(CF_UNICODETEXT);打不开剪贴板时静默放弃。"""
    CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
    data = (text + "\0").encode("utf-16-le")
    if not user32.OpenClipboard(hwnd):
        if debug:
            print("[TD] clipboard: OpenClipboard failed", flush=True)
        return
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        p = kernel32.GlobalLock(h)
        if p:
            ctypes.memmove(p, data, len(data))
            kernel32.GlobalUnlock(h)
        ok = user32.SetClipboardData(CF_UNICODETEXT, h)
        if debug:
            print(
                f"[TD] clipboard: SetClipboardData -> {bool(ok)} ({len(data)}B)",
                flush=True,
            )
    finally:
        user32.CloseClipboard()
