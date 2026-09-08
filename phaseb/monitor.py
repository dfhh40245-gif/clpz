"""Phase B resource monitor.

Samples a process tree (server + children) for RAM, CPU, process count and
disk usage of a data dir, printing a timeline. Windows-safe via CIM/WMI.

Usage: python monitor.py <server_pid> <watch_dir> <interval_seconds>
Runs until killed; prints one line per sample to stdout (flushed).
"""
import subprocess
import sys
import time
from pathlib import Path


def sample(pid: int, watch_dir: str) -> str:
    ps = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.ParentProcessId -eq {pid} -or $_.ProcessId -eq {pid} }} | "
        "Select-Object ProcessId, Name, WorkingSetSize | ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    except Exception as e:
        return f"ERR ps={e}"

    import json
    total_ram = 0
    count = 0
    names = []
    if out:
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        for p in data:
            total_ram += int(p.get("WorkingSetSize", 0))
            count += 1
            names.append(p.get("Name", "?").replace(".exe", ""))

    # system-wide free RAM
    try:
        free = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
            capture_output=True, text=True, timeout=15).stdout.strip()
        free_gb = int(free) / 1024 / 1024
    except Exception:
        free_gb = -1

    # dir size
    dir_mb = 0
    try:
        d = Path(watch_dir)
        if d.exists():
            dir_mb = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1e6
    except Exception:
        pass

    return (f"procs={count} [{','.join(names[:6])}] "
            f"tree_ram={total_ram/1e6:.0f}MB free_sys={free_gb:.2f}GB "
            f"dir={dir_mb:.1f}MB")


def main():
    pid = int(sys.argv[1])
    watch = sys.argv[2]
    interval = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
    while True:
        print(f"{time.strftime('%H:%M:%S')} {sample(pid, watch)}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
