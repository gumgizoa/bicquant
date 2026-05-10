# Purpose: Crawl `LS증권` HTS stock screening ([1892](KRX) 조건검색) results.
# There is no open API or Xing-API available to retrieve "historical" stock screening results (과거 시점 조건검색).
# This script automates interaction with the Parallels Desktop virtual machine. It connects via SSH and runs Python code to automate computer use tasks on the VM.

# It must ensures:
# 1. The LS Securities (LS증권) application ("투혼") is already running.
# 2. The [1892](KRX) stock screening window is open and at the front.
# 3. The "과거시점검색" (historical search) option is enabled, and the timestamp is set to "종가" (closing price).

# Usage:
#   ===== (Ensure `bridge.py` is run on Windows VM) =====
#   python crawl_hts.py              # test mode: only 360 days ago (2025-05-15)
#   python crawl_hts.py --all        # full run: 360 days ago to today (weekdays only)
#   python crawl_hts.py --diagnose   # print VM window/control tree for debugging

import argparse
import base64
import os
import re
import subprocess
import textwrap
import time
from datetime import date, timedelta

import paramiko
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# VM path constants
# ---------------------------------------------------------------------------

VENV_PYTHON = r"C:\Users\cho-eungi\eungizoa\bicquant\Scripts\python.exe"
REMOTE_SCRIPT = r"C:\Users\cho-eungi\AppData\Local\Temp\hts_automation.py"
REMOTE_LOG = r"C:\Users\cho-eungi\AppData\Local\Temp\hts_automation.log"
REMOTE_DONE = r"C:\Users\cho-eungi\AppData\Local\Temp\hts_automation.done"
REMOTE_TRIGGER = r"C:\Users\cho-eungi\AppData\Local\Temp\hts_trigger.txt"


# ---------------------------------------------------------------------------
# SSH infrastructure
# ---------------------------------------------------------------------------


def get_parallels_ip(vm_name: str = "Windows 11") -> str:
    result = subprocess.run(
        ["/usr/local/bin/prlctl", "list", "--info", vm_name],
        capture_output=True,
        text=True,
    )
    match = re.search(r"IP Addresses:\s*([\d.]+)", result.stdout)
    if match:
        return match.group(1)
    raise RuntimeError(f"Parallels VM IP not found for '{vm_name}'.")


def connect_ssh(
    host: str,
    username: str | None = None,
    password: str | None = None,
    timeout: int = 10,
) -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        host,
        username=username or os.getenv("PRL_USERNAME"),
        password=password or os.getenv("PRL_PASSWORD"),
        timeout=timeout,
        banner_timeout=timeout,
        auth_timeout=timeout,
    )
    return ssh


def ssh_run(ssh: paramiko.SSHClient, cmd: str) -> tuple[str, str, int]:
    """Run a shell command on the VM and return (stdout, stderr, exit_status)."""
    _, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out, err, stdout.channel.recv_exit_status()


# ---------------------------------------------------------------------------
# Task Scheduler execution engine
# SSH session runs in Session 0 (no desktop access). We write the script to
# a file and trigger it via schtasks /it so it runs in the interactive session.
# ---------------------------------------------------------------------------


def write_script_to_vm(ssh: paramiko.SSHClient, code: str) -> None:
    """Wrap code with log redirection and write it to the VM via PowerShell."""
    wrapped = (
        "import sys as _sys, traceback as _tb\n"
        f'_sys.stdout = open(r"{REMOTE_LOG}", "w", encoding="utf-8", buffering=1)\n'
        "_sys.stderr = _sys.stdout\n"
        "try:\n" + textwrap.indent(code, "    ") + "\n"
        "except Exception as _e:\n"
        "    _tb.print_exc()\n"
        "finally:\n"
        "    _sys.stdout.flush()\n"
        f'    open(r"{REMOTE_DONE}", "w").write("done")\n'
    )

    # Encode the script as base64 to avoid any quoting/encoding issues
    code_b64 = base64.b64encode(wrapped.encode("utf-8")).decode("ascii")

    # Write base64 in chunks to avoid cmd/PowerShell 8191-char line-length limit.
    # First chunk: create the file; subsequent chunks: append.
    CHUNK = 2000
    chunks = [code_b64[i : i + CHUNK] for i in range(0, len(code_b64), CHUNK)]
    tmp_b64 = REMOTE_SCRIPT + ".b64"

    for idx, chunk in enumerate(chunks):
        redirect = ">" if idx == 0 else ">>"
        out, err, status = ssh_run(ssh, f'echo {chunk} {redirect} "{tmp_b64}"')
        if status != 0:
            raise RuntimeError(f"Failed to write b64 chunk {idx}:\n{err}\n{out}")

    # Decode the b64 file → final script file via PowerShell
    ps_script = (
        f"$b=[System.IO.File]::ReadAllText('{tmp_b64}').Trim();"
        f"$d=[System.Convert]::FromBase64String($b);"
        f"[System.IO.File]::WriteAllBytes('{REMOTE_SCRIPT}',$d);"
        f"Remove-Item '{tmp_b64}'"
    )
    ps_b64 = base64.b64encode(ps_script.encode("utf-16-le")).decode("ascii")
    out, err, status = ssh_run(ssh, f"powershell -EncodedCommand {ps_b64}")
    if status != 0:
        raise RuntimeError(f"Failed to write script to VM:\n{err}\n{out}")
    print("Script written to VM.", flush=True)


def cleanup_vm_artifacts(ssh: paramiko.SSHClient) -> None:
    """Delete stale log/done files before a new run."""
    for path in (REMOTE_LOG, REMOTE_DONE):
        ssh_run(ssh, f'del /f "{path}" 2>nul')
    time.sleep(0.3)


def trigger_bridge(ssh: paramiko.SSHClient) -> None:
    """Write the trigger file so the bridge script (running on the VM's desktop) picks it up.

    The bridge (parallels/bridge.py) must already be running in an interactive
    CMD window on the VM. It watches for REMOTE_TRIGGER every 0.5 s and
    executes hts_automation.py in that session (full desktop access).
    """
    out, err, status = ssh_run(ssh, f'echo trigger > "{REMOTE_TRIGGER}"')
    if status != 0:
        raise RuntimeError(f"Failed to write trigger file:\n{err}\n{out}")
    print("Trigger sent. Waiting for bridge to pick it up...", flush=True)


def kill_vm_automation(ssh: paramiko.SSHClient) -> None:
    """Kill hts_automation.py on the VM (leaves bridge.py running if possible)."""
    ps = (
        "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" "
        "| Where-Object { $_.CommandLine -like '*hts_automation*' } "
        '| ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Output "Killed PID $($_.ProcessId)" }'
    )
    ps_b64 = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
    out, err, _ = ssh_run(ssh, f"powershell -EncodedCommand {ps_b64}")
    result = (out + err).strip()
    print(f"[kill] {result or 'no matching process found'}", flush=True)


def stream_log_until_done(ssh: paramiko.SSHClient, timeout: int = 7200) -> str:
    """Poll every 2 s: print new log lines in real-time, return when done sentinel appears."""
    last_size = 0

    try:
        for _ in range(timeout // 2):
            time.sleep(2)

            # Read current log content
            out, _, _ = ssh_run(ssh, f'type "{REMOTE_LOG}" 2>nul')
            if len(out) > last_size:
                new_text = out[last_size:]
                for line in new_text.splitlines():
                    print(f"[VM] {line}", flush=True)
                last_size = len(out)

            # Check for sentinel
            done_out, _, _ = ssh_run(ssh, f'if exist "{REMOTE_DONE}" echo yes')
            if "yes" in done_out:
                return out

    except KeyboardInterrupt:
        print("\n[Ctrl+C] 중단 요청 — VM 스크립트 종료 중...", flush=True)
        kill_vm_automation(ssh)
        raise

    raise TimeoutError(f"Script did not complete within {timeout}s")


# ---------------------------------------------------------------------------
# Date utilities
# ---------------------------------------------------------------------------


def generate_date_pairs(
    start_days_ago: int = 360,
    end_days_ago: int = 0,
    reference_date: date | None = None,
) -> list[tuple[str, int]]:
    """Return (date_str, n_days) pairs for each weekday in [start, end].

    n_days = calendar days from reference_date back to that date — the value
    entered in the HTS "오늘기준 N일 전" field.
    """
    if reference_date is None:
        reference_date = date.today()

    pairs: list[tuple[str, int]] = []
    current = reference_date - timedelta(days=start_days_ago)
    end = reference_date - timedelta(days=end_days_ago)

    while current <= end:
        if current.weekday() < 5:
            n_days = (reference_date - current).days
            pairs.append((current.strftime("%Y-%m-%d"), n_days))
        current += timedelta(days=1)

    return pairs


# ---------------------------------------------------------------------------
# Remote code: diagnose mode
# ---------------------------------------------------------------------------

DIAGNOSE_EXCEL_CODE = r"""
import time
from pywinauto import Application, Desktop

app = Application(backend="uia").connect(title="LS증권 투혼", timeout=5)
main_win = app.window(title="LS증권 투혼")
child = main_win.child_window(title_re=r"\[1892\].*조건검색", control_type="Window")
print(f"[1892] window: '{child.window_text()}'", flush=True)

print("\n=== Clicking 종목전송 ===", flush=True)
btn = child.child_window(title="종목전송", auto_id="4100", control_type="Button")
btn.click_input()
time.sleep(1.0)

print("\n=== Top-level windows after 종목전송 click ===", flush=True)
desktop = Desktop(backend="uia")
for w in desktop.windows():
    try:
        t = w.window_text()
        c = w.class_name()
        r = w.rectangle()
        print(f"  '{t}' class='{c}' rect={r}", flush=True)
        # Print descendants of small/new windows
        if c in ('#32768', 'tooltips_class32') or (t == '' and r.width() < 400 and r.height() < 400 and r.width() > 0):
            for ctrl in w.descendants():
                try:
                    ei = ctrl.element_info
                    ct = getattr(ei, 'control_type', '?')
                    aid = getattr(ei, 'automation_id', None) or getattr(ei, 'auto_id', '?')
                    print(f"      [{ct}] auto_id={aid!r} text={ctrl.window_text()!r} rect={ctrl.rectangle()}", flush=True)
                except Exception as e2:
                    print(f"      error: {e2}", flush=True)
    except Exception:
        pass

print("\n=== All new descendants of main_win (Button/MenuItem/ListItem/Custom) ===", flush=True)
for ctrl in main_win.descendants():
    try:
        ei = ctrl.element_info
        ct = getattr(ei, 'control_type', '')
        if ct in ('Button', 'MenuItem', 'ListItem', 'Custom', 'List', 'Menu'):
            aid = getattr(ei, 'automation_id', None) or getattr(ei, 'auto_id', '?')
            txt = ctrl.window_text()
            print(f"  [{ct}] auto_id={aid!r} text={txt!r} rect={ctrl.rectangle()}", flush=True)
    except Exception as e:
        print(f"  error: {e}", flush=True)

print("\n=== Done ===", flush=True)
"""

DIAGNOSE_CODE = r"""
import time
from pywinauto import Application, Desktop

app = Application(backend="uia").connect(title="LS증권 투혼", timeout=5)
main_win = app.window(title="LS증권 투혼")
child = main_win.child_window(title_re=r"\[1892\].*조건검색", control_type="Window")
print(f"[1892] window: '{child.window_text()}'", flush=True)

def ctrl_info(ctrl):
    ei = ctrl.element_info
    aid = getattr(ei, 'automation_id', None) or getattr(ei, 'auto_id', '?')
    ct = getattr(ei, 'control_type', '?')
    return f"type={ct} auto_id={aid!r} text={ctrl.window_text()!r} rect={ctrl.rectangle()}"

# --- Step 1: date pane descendants ---
print("\n=== Date pane (auto_id=10695) descendants ===", flush=True)
date_pane = child.child_window(auto_id="10695", control_type="Pane")
print(f"  date_pane rect: {date_pane.rectangle()}", flush=True)
for ctrl in date_pane.descendants():
    try:
        print(f"  {ctrl_info(ctrl)}", flush=True)
    except Exception as e:
        print(f"  error: {e}", flush=True)

# --- Step 2: click ▼ and capture popup ---
print("\n=== Clicking ▼ (auto_id=20001 inside 10695) ===", flush=True)
dropdown_btn = date_pane.child_window(auto_id="20001", control_type="Button")
dropdown_btn.click_input()
time.sleep(1.5)

# --- All descendants of main_win after click (popup may be at main level) ---
print("\n=== All Edit/Pane/Window descendants of main_win after click ===", flush=True)
for ctrl in main_win.descendants():
    try:
        ei = ctrl.element_info
        ct = getattr(ei, 'control_type', '')
        if ct in ('Edit', 'Pane', 'Window', 'Group'):
            aid = getattr(ei, 'automation_id', None) or getattr(ei, 'auto_id', '?')
            print(f"  {ct} auto_id={aid!r} text={ctrl.window_text()!r} rect={ctrl.rectangle()}", flush=True)
    except Exception as e:
        print(f"  error: {e}", flush=True)

# --- All new top-level windows ---
print("\n=== Top-level windows after click ===", flush=True)
desktop = Desktop(backend="uia")
for w in desktop.windows():
    try:
        t = w.window_text()
        if t:
            print(f"  '{t}' class='{w.class_name()}'", flush=True)
    except Exception:
        pass

print("\n=== Done ===", flush=True)
"""


# ---------------------------------------------------------------------------
# Remote code: automation
# Use __DATE_PAIRS__ as the sole injection point to avoid escaping { }.
# ---------------------------------------------------------------------------

_AUTOMATION_TEMPLATE = r"""
import re
import sys
import time
import pyperclip
from pywinauto import Desktop, Application
from pywinauto.keyboard import send_keys

DATE_PAIRS = __DATE_PAIRS__


def find_hts_window():
    # Connect to 투혼 and return (child_window, main_win, backend).
    app = Application(backend="uia").connect(title="LS증권 투혼", timeout=10)
    main_win = app.window(title="LS증권 투혼")
    child = main_win.child_window(title_re=r"\[1892\].*조건검색", control_type="Window")
    child.set_focus()
    print(f"Found: '{child.window_text()}'", flush=True)
    return child, main_win, "uia"


def set_date(win, main_win, n_days, backend):
    # Click ▼ in the date pane, then enter n_days in the popup edit field.
    # Popup Edit auto_id="20102" appears as a descendant of main_win (not child).

    date_pane = win.child_window(auto_id="10695", control_type="Pane")
    dropdown_btn = date_pane.child_window(auto_id="20001", control_type="Button")
    dropdown_btn.click_input()
    time.sleep(1.0)

    # Wait for popup Edit (auto_id="20102") to appear as a descendant of main_win
    edit = None
    for _ in range(20):
        try:
            for ctrl in main_win.descendants(control_type="Edit"):
                ei = ctrl.element_info
                aid = getattr(ei, 'automation_id', None) or getattr(ei, 'auto_id', '')
                if aid == '20102':
                    edit = ctrl
                    break
        except Exception:
            pass
        if edit:
            break
        time.sleep(0.2)

    if not edit:
        raise RuntimeError("오늘기준 edit field (auto_id=20102) not found after clicking dropdown")

    # Clear field and type value
    edit.click_input()
    time.sleep(0.1)
    send_keys("^a")
    send_keys(str(n_days))
    send_keys("{ENTER}")
    time.sleep(0.5)


def run_search(win):
    # Click the main 검색 button (auto_id="4040") and wait for results.
    btn = win.child_window(title="검색", auto_id="4040", control_type="Button")
    btn.click_input()
    print("  Clicked 검색, waiting for results...", flush=True)

    # The result ComboBox (auto_id="6390") shows "(검색결과 : N개)" when done.
    result_combo = win.child_window(auto_id="6390", control_type="ComboBox")
    for _ in range(60):
        time.sleep(0.5)
        try:
            t = result_combo.window_text()
            if "검색결과" in t:
                print(f"  {t}", flush=True)
                return
        except Exception:
            pass

    raise TimeoutError("검색 did not complete within 30 s")


def export_excel(win, main_win, date_str, backend):
    # Click 종목전송 > EXCEL > save dialog > save as date_str.xlsx.
    desktop = Desktop(backend=backend)

    btn = win.child_window(title="종목전송", auto_id="4100", control_type="Button")
    btn.click_input()
    time.sleep(0.5)

    # Wait for context menu (#32768) and click EXCEL item (auto_id="11040")
    excel_clicked = False
    for _ in range(20):
        time.sleep(0.2)
        try:
            menu = desktop.window(class_name="#32768")
            if menu.exists(timeout=0.1):
                item = menu.child_window(auto_id="11040", control_type="MenuItem")
                item.click_input()
                excel_clicked = True
                break
        except Exception:
            pass

    if not excel_clicked:
        raise RuntimeError("Could not click EXCEL menu item (auto_id=11040)")

    time.sleep(1.5)

    # Save dialog may be a child of main_win OR a top-level window
    save_dlg = None
    for _ in range(30):
        time.sleep(0.3)
        # Try top-level first (returns WindowSpecification — has child_window)
        try:
            dlg = desktop.window(title="다른 이름으로 저장")
            if dlg.exists(timeout=0.1):
                save_dlg = dlg
                break
        except Exception:
            pass
        # Try as child of main HTS window; wrap via Application.connect to get WindowSpecification
        try:
            for w in main_win.descendants(control_type="Window"):
                if "저장" in w.window_text():
                    app2 = Application(backend=backend).connect(handle=w.handle)
                    save_dlg = app2.window(handle=w.handle)
                    break
        except Exception:
            pass
        if save_dlg:
            break

    if not save_dlg:
        raise RuntimeError("Save dialog did not appear")

    # Find the filename Edit — auto_id="1001" in standard Windows dialog
    fn_edit = None
    for candidate_id in ("1001", "FileNameControlHost"):
        try:
            e = save_dlg.child_window(auto_id=candidate_id, control_type="Edit")
            if e.exists(timeout=0.3):
                fn_edit = e
                break
        except Exception:
            pass
    if not fn_edit:
        edits = save_dlg.descendants(control_type="Edit")
        if edits:
            fn_edit = edits[0]
    if not fn_edit:
        raise RuntimeError("Filename Edit not found in save dialog")

    fn_edit.click_input()
    send_keys("^a")
    time.sleep(0.1)
    send_keys(f"{date_str}.xlsx", with_spaces=True)
    time.sleep(0.2)

    save_btn = save_dlg.child_window(title="저장(S)", control_type="Button")
    save_btn.click_input()
    time.sleep(1.0)
    print(f"  Saved: {date_str}.xlsx", flush=True)


def main():
    if not DATE_PAIRS:
        print("DATE_PAIRS is empty.", flush=True)
        return

    start_date = DATE_PAIRS[0][0]
    end_date = DATE_PAIRS[-1][0]
    print(f"Starting automation for {len(DATE_PAIRS)} date(s): {start_date} ~ {end_date}", flush=True)
    win, main_win, backend = find_hts_window()
    errors = []

    for i, (date_str, n_days) in enumerate(DATE_PAIRS):
        print(f"[{i + 1}/{len(DATE_PAIRS)}] {date_str} (N={n_days})", flush=True)
        try:
            # Re-connect if the window reference has gone stale
            try:
                win.window_text()
            except Exception:
                print("  [reconnect] HTS window lost, reconnecting...", flush=True)
                win, main_win, backend = find_hts_window()
            set_date(win, main_win, n_days, backend)
            run_search(win)
            export_excel(win, main_win, date_str, backend)
        except Exception as e:
            msg = f"ERROR on {date_str}: {e}"
            print(f"  {msg}", flush=True)
            errors.append(msg)

    print(f"\nDone. {len(DATE_PAIRS) - len(errors)}/{len(DATE_PAIRS)} succeeded.", flush=True)
    if errors:
        print("Failed dates:", flush=True)
        for e in errors:
            print(f"  {e}", flush=True)


main()
"""


def build_remote_code(date_pairs: list[tuple[str, int]]) -> str:
    return _AUTOMATION_TEMPLATE.replace("__DATE_PAIRS__", repr(date_pairs))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automate LS HTS [1892] condition search download."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--all",
        action="store_true",
        help="Download all weekdays from 360 days ago to today.",
    )
    group.add_argument(
        "--diagnose",
        action="store_true",
        help="Print VM window/control tree for debugging.",
    )
    group.add_argument(
        "--diagnose-excel",
        action="store_true",
        help="Debug 종목전송 dropdown structure.",
    )
    group.add_argument(
        "--kill",
        action="store_true",
        help="Kill hts_automation.py on the VM immediately.",
    )
    parser.add_argument(
        "--start", type=int, default=None, help="Start N days ago (inclusive). e.g. 360"
    )
    parser.add_argument(
        "--end", type=int, default=None, help="End N days ago (inclusive). e.g. 301"
    )
    args = parser.parse_args()

    prl_ip = get_parallels_ip()
    print(f"PRL IP: {prl_ip}")

    ssh = connect_ssh(prl_ip)
    try:
        if args.kill:
            print("VM 스크립트 강제 종료 중...")
            kill_vm_automation(ssh)
            return
        elif args.diagnose:
            print("Running diagnose mode...")
            code = DIAGNOSE_CODE
        elif args.diagnose_excel:
            print("Running excel diagnose mode (검색 결과가 있어야 합니다)...")
            code = DIAGNOSE_EXCEL_CODE
        elif args.start is not None or args.end is not None:
            start = args.start if args.start is not None else 360
            end = args.end if args.end is not None else 0
            date_pairs = generate_date_pairs(start_days_ago=start, end_days_ago=end)
            print(f"Range run ({start}~{end} days ago): {len(date_pairs)} trading days")
            code = build_remote_code(date_pairs)
        elif args.all:
            date_pairs = generate_date_pairs(start_days_ago=360, end_days_ago=0)
            print(f"Full run: {len(date_pairs)} trading days")
            code = build_remote_code(date_pairs)
        else:
            date_pairs = generate_date_pairs(start_days_ago=360, end_days_ago=360)
            print(f"Test mode: {date_pairs}")
            code = build_remote_code(date_pairs)

        cleanup_vm_artifacts(ssh)
        write_script_to_vm(ssh, code)
        trigger_bridge(ssh)
        try:
            stream_log_until_done(ssh)
        finally:
            # Always kill any remaining VM python process after completion or error.
            # If the SSH session dropped (ConnectionResetError / SSHException),
            # open a fresh connection so we can still kill the automation on the VM.
            try:
                kill_vm_automation(ssh)
            except (paramiko.SSHException, ConnectionResetError, OSError) as e:
                print(
                    f"[kill] SSH session dead ({e}), reconnecting to kill VM process...",
                    flush=True,
                )
                try:
                    ssh2 = connect_ssh(prl_ip)
                    kill_vm_automation(ssh2)
                    ssh2.close()
                except Exception as e2:
                    print(
                        f"[kill] Reconnect failed — VM process may still be running: {e2}",
                        flush=True,
                    )

    finally:
        ssh.close()


if __name__ == "__main__":
    main()
