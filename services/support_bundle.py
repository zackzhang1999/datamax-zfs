"""
Support Bundle Service
Collects system diagnostic data and packages it into a downloadable zip file
for sharing with support or community assistance.
"""
import io
import json
import os
import platform
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from services.utils import (
    get_os_type,
    is_freebsd,
    is_netbsd,
    is_linux,
    run_zfs_command,
    run_privileged_command,
    get_zfs_version,
)
from services.audit_logger import audit_logger, LogCategory


class SupportBundleService:
    """
    Collects selected diagnostic data items and produces an in-memory
    zip archive that can be streamed back to the user.
    """

    # ------------------------------------------------------------------ #
    #  Data collection registry                                          #
    # ------------------------------------------------------------------ #
    # Each item is (key, label, description, category)
    DATA_ITEMS = [
        # ZFS Pool Information
        (
            "zpool_status",
            "zpool status",
            "所有 ZFS 存储池的详细状态，包括设备布局和错误",
            "ZFS 存储池信息",
        ),
        (
            "zpool_list",
            "zpool list",
            "所有 ZFS 存储池的摘要，包括大小、分配和健康状况",
            "ZFS 存储池信息",
        ),
        (
            "zpool_get_all",
            "zpool get all",
            "每个 ZFS 存储池的所有属性",
            "ZFS 存储池信息",
        ),
        (
            "pool_history",
            "存储池历史记录",
            "所有 ZFS 存储池的近期命令历史",
            "ZFS 存储池信息",
        ),
        (
            "pool_events",
            "存储池事件",
            "ZFS 存储池事件日志条目",
            "ZFS 存储池信息",
        ),
        # ZFS Dataset / Snapshot Information
        (
            "zfs_list",
            "zfs list",
            "所有数据集的已用、可用、引用量和挂载点信息",
            "ZFS 数据集信息",
        ),
        (
            "zfs_get_all",
            "zfs get all",
            "每个数据集的所有属性（内容可能很大）",
            "ZFS 数据集信息",
        ),
        (
            "snapshot_list",
            "快照列表",
            "来自 zfs list -t snapshot 的所有快照",
            "ZFS 数据集信息",
        ),
        # ZFS Module / Kernel
        (
            "zfs_version",
            "ZFS 版本",
            "已安装的 ZFS 版本信息",
            "ZFS 模块 / 内核",
        ),
        (
            "module_parameters",
            "ZFS 模块参数",
            "当前所有 ZFS 内核模块参数值",
            "ZFS 模块 / 内核",
        ),
        # System Logs
        (
            "syslog_zfs",
            "系统日志（ZFS 条目）",
            "系统日志中与 ZFS 相关的条目",
            "系统日志",
        ),
        (
            "zfs_debug_log",
            "ZFS 调试日志",
            "ZFS 内核调试消息（/proc/spl/kstat/zfs/dbgmsg 或 sysctl）",
            "系统日志",
        ),
        (
            "dmesg",
            "dmesg 输出",
            "内核环形缓冲区消息（完整 dmesg）",
            "系统日志",
        ),
        # System Information
        (
            "system_info",
            "系统信息",
            "操作系统、内核、主机名、架构、运行时间和内存",
            "系统信息",
        ),
        # Health Reports
        (
            "health_reports",
            "健康分析报告",
            "之前保存的健康分析报告数据",
            "健康报告",
        ),
        # Audit Logs
        (
            "audit_logs",
            "WebZFS 审计日志",
            "认证、ZFS 操作和文件访问审计日志",
            "审计日志",
        ),
    ]

    def get_data_items(self) -> List[Dict]:
        """Return the full list of collectable data items grouped by category."""
        items = []
        for key, label, description, category in self.DATA_ITEMS:
            items.append(
                {
                    "key": key,
                    "label": label,
                    "description": description,
                    "category": category,
                }
            )
        return items

    # ------------------------------------------------------------------ #
    #  Bundle generation                                                 #
    # ------------------------------------------------------------------ #

    def generate_bundle(self, selected_keys: List[str]) -> io.BytesIO:
        """
        Collect the requested data items and return an in-memory zip file.

        Args:
            selected_keys: list of item keys the user selected.

        Returns:
            io.BytesIO containing the zip archive.
        """
        buffer = io.BytesIO()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hostname = platform.node() or "unknown"
        prefix = f"webzfs-support-{hostname}-{timestamp}"

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Always include a manifest
            manifest_lines = [
                f"WebZFS Support Bundle",
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Hostname: {hostname}",
                f"OS: {get_os_type()} {platform.release()}",
                f"Items included: {', '.join(selected_keys)}",
            ]
            zf.writestr(
                f"{prefix}/MANIFEST.txt", "\n".join(manifest_lines) + "\n"
            )

            # Dispatch each selected item to its collector
            collectors = {
                "zpool_status": self._collect_zpool_status,
                "zpool_list": self._collect_zpool_list,
                "zpool_get_all": self._collect_zpool_get_all,
                "pool_history": self._collect_pool_history,
                "pool_events": self._collect_pool_events,
                "zfs_list": self._collect_zfs_list,
                "zfs_get_all": self._collect_zfs_get_all,
                "snapshot_list": self._collect_snapshot_list,
                "zfs_version": self._collect_zfs_version,
                "module_parameters": self._collect_module_parameters,
                "syslog_zfs": self._collect_syslog_zfs,
                "zfs_debug_log": self._collect_zfs_debug_log,
                "dmesg": self._collect_dmesg,
                "system_info": self._collect_system_info,
                "health_reports": self._collect_health_reports,
                "audit_logs": self._collect_audit_logs,
            }

            for key in selected_keys:
                collector = collectors.get(key)
                if collector is None:
                    continue
                try:
                    filename, content = collector()
                    zf.writestr(f"{prefix}/{filename}", content)
                except Exception as exc:
                    error_text = f"Error collecting {key}: {exc}\n"
                    zf.writestr(f"{prefix}/{key}_ERROR.txt", error_text)

        buffer.seek(0)
        return buffer

    # ------------------------------------------------------------------ #
    #  Individual collectors                                             #
    #  Each returns (filename, text_content).                            #
    # ------------------------------------------------------------------ #

    def _run_cmd(
        self, cmd: List[str], timeout: float = 30, use_zfs: bool = True
    ) -> str:
        """Helper to run a command and return stdout, falling back to stderr."""
        try:
            if use_zfs:
                result = run_zfs_command(
                    cmd, check=False, timeout=timeout
                )
            else:
                result = run_privileged_command(
                    cmd, check=False, timeout=timeout
                )
            output = result.stdout or ""
            if result.returncode != 0 and result.stderr:
                output += f"\n--- stderr ---\n{result.stderr}"
            return output
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout}s: {' '.join(cmd)}\n"
        except Exception as exc:
            return f"Command failed: {exc}\n"

    # -- ZFS Pool Information --

    def _collect_zpool_status(self):
        return ("zpool_status.txt", self._run_cmd(["zpool", "status", "-v"]))

    def _collect_zpool_list(self):
        return (
            "zpool_list.txt",
            self._run_cmd(
                ["zpool", "list", "-v", "-o",
                 "name,size,alloc,free,frag,cap,dedup,health"]
            ),
        )

    def _collect_zpool_get_all(self):
        return ("zpool_get_all.txt", self._run_cmd(["zpool", "get", "all"]))

    def _collect_pool_history(self):
        return (
            "pool_history.txt",
            self._run_cmd(["zpool", "history", "-l"], timeout=60),
        )

    def _collect_pool_events(self):
        if is_netbsd():
            return ("pool_events.txt", "Pool events not supported on NetBSD.\n")
        return (
            "pool_events.txt",
            self._run_cmd(["zpool", "events", "-v"], timeout=30),
        )

    # -- ZFS Dataset / Snapshot Information --

    def _collect_zfs_list(self):
        return (
            "zfs_list.txt",
            self._run_cmd(
                ["zfs", "list", "-o",
                 "name,used,avail,refer,mountpoint,type,origin,compress,atime"]
            ),
        )

    def _collect_zfs_get_all(self):
        return (
            "zfs_get_all.txt",
            self._run_cmd(["zfs", "get", "all"], timeout=60),
        )

    def _collect_snapshot_list(self):
        return (
            "snapshot_list.txt",
            self._run_cmd(
                ["zfs", "list", "-t", "snapshot", "-o",
                 "name,used,refer,creation"]
            ),
        )

    # -- ZFS Module / Kernel --

    def _collect_zfs_version(self):
        version_output = get_zfs_version() or "Could not determine ZFS version."
        # Also grab zpool upgrade -v for feature flags
        feature_flags = self._run_cmd(
            ["zpool", "upgrade", "-v"], timeout=10
        )
        return (
            "zfs_version.txt",
            f"{version_output}\n\n--- Feature Flags ---\n{feature_flags}",
        )

    def _collect_module_parameters(self):
        if is_linux():
            return self._collect_module_parameters_linux()
        elif is_freebsd() or is_netbsd():
            return self._collect_module_parameters_bsd()
        return ("module_parameters.txt", "Unsupported platform.\n")

    def _collect_module_parameters_linux(self):
        params_dir = Path("/sys/module/zfs/parameters")
        if not params_dir.exists():
            return (
                "module_parameters.txt",
                "ZFS module parameters directory not found.\n",
            )
        lines = []
        try:
            for param_file in sorted(params_dir.iterdir()):
                if param_file.is_file():
                    try:
                        value = param_file.read_text().strip()
                        lines.append(f"{param_file.name} = {value}")
                    except Exception:
                        lines.append(f"{param_file.name} = <unreadable>")
        except Exception as exc:
            lines.append(f"Error reading parameters: {exc}")
        return ("module_parameters.txt", "\n".join(lines) + "\n")

    def _collect_module_parameters_bsd(self):
        try:
            result = run_privileged_command(
                ["sysctl", "-a"],
                check=False,
                timeout=15,
            )
            # Filter for ZFS-related sysctl values
            zfs_lines = []
            for line in (result.stdout or "").splitlines():
                lower = line.lower()
                if "zfs" in lower or "vfs.zfs" in lower:
                    zfs_lines.append(line)
            if not zfs_lines:
                return (
                    "module_parameters.txt",
                    "No ZFS sysctl parameters found.\n",
                )
            return ("module_parameters.txt", "\n".join(zfs_lines) + "\n")
        except Exception as exc:
            return ("module_parameters.txt", f"Error: {exc}\n")

    # -- System Logs --

    def _collect_syslog_zfs(self):
        if is_linux():
            # Try journalctl first
            try:
                result = run_privileged_command(
                    [
                        "journalctl",
                        "-k",
                        "--no-pager",
                        "-n",
                        "2000",
                        "--grep",
                        "zfs|zpool|spl",
                    ],
                    check=False,
                    timeout=15,
                )
                if result.returncode == 0 and result.stdout:
                    return ("syslog_zfs.txt", result.stdout)
            except Exception:
                pass
            # Fallback: grep /var/log/syslog or /var/log/messages
            for log_path in ["/var/log/syslog", "/var/log/messages"]:
                if Path(log_path).exists():
                    try:
                        result = run_privileged_command(
                            ["grep", "-i", "zfs\\|zpool", log_path],
                            check=False,
                            timeout=15,
                        )
                        if result.stdout:
                            # Return last 2000 lines
                            lines = result.stdout.splitlines()[-2000:]
                            return ("syslog_zfs.txt", "\n".join(lines) + "\n")
                    except Exception:
                        continue
            return ("syslog_zfs.txt", "No ZFS syslog entries found.\n")
        else:
            # BSD: grep /var/log/messages
            try:
                result = run_privileged_command(
                    [
                        "sh",
                        "-c",
                        'grep -i "zfs\\|zpool" /var/log/messages | tail -n 2000',
                    ],
                    check=False,
                    timeout=15,
                    use_sudo=False,
                )
                if result.stdout:
                    return ("syslog_zfs.txt", result.stdout)
            except Exception:
                pass
            return ("syslog_zfs.txt", "No ZFS syslog entries found.\n")

    def _collect_zfs_debug_log(self):
        if is_linux():
            dbgmsg_path = Path("/proc/spl/kstat/zfs/dbgmsg")
            if dbgmsg_path.exists():
                try:
                    result = run_privileged_command(
                        ["cat", "/proc/spl/kstat/zfs/dbgmsg"],
                        check=False,
                        timeout=10,
                    )
                    return ("zfs_debug_log.txt", result.stdout or "Empty.\n")
                except Exception as exc:
                    return ("zfs_debug_log.txt", f"Error: {exc}\n")
            return (
                "zfs_debug_log.txt",
                "Debug log not available (/proc/spl/kstat/zfs/dbgmsg missing).\n",
            )
        else:
            # BSD: sysctl
            for key in [
                "kstat.zfs.misc.dbgmsg",
                "vfs.zfs.dbgmsg",
            ]:
                try:
                    result = subprocess.run(
                        ["sysctl", "-n", key],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=10,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        return ("zfs_debug_log.txt", result.stdout)
                except Exception:
                    continue
            return (
                "zfs_debug_log.txt",
                "ZFS debug log not available via sysctl.\n",
            )

    def _collect_dmesg(self):
        if is_freebsd() or is_netbsd():
            return ("dmesg.txt", self._run_cmd(["dmesg"], use_zfs=False))
        return ("dmesg.txt", self._run_cmd(["dmesg", "-T"], use_zfs=False))

    # -- System Information --

    def _collect_system_info(self):
        lines = []
        lines.append(f"Hostname: {platform.node()}")
        lines.append(f"OS: {get_os_type()}")
        lines.append(f"Platform: {platform.platform()}")
        lines.append(f"Kernel: {platform.release()}")
        lines.append(f"Architecture: {platform.machine()}")
        lines.append(f"Processor: {platform.processor()}")
        lines.append(f"Python: {platform.python_version()}")

        # Uptime
        try:
            if is_linux():
                with open("/proc/uptime", "r") as f:
                    uptime_seconds = float(f.read().split()[0])
                    days = int(uptime_seconds // 86400)
                    hours = int((uptime_seconds % 86400) // 3600)
                    minutes = int((uptime_seconds % 3600) // 60)
                    lines.append(
                        f"Uptime: {days}d {hours}h {minutes}m"
                    )
            else:
                result = subprocess.run(
                    ["uptime"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                if result.stdout:
                    lines.append(f"Uptime: {result.stdout.strip()}")
        except Exception:
            lines.append("Uptime: unavailable")

        # Memory
        try:
            import psutil

            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024 ** 3)
            used_gb = mem.used / (1024 ** 3)
            lines.append(
                f"Memory: {used_gb:.1f} GB / {total_gb:.1f} GB "
                f"({mem.percent}% used)"
            )
        except Exception:
            lines.append("Memory: unavailable")

        # CPU count
        try:
            lines.append(f"CPU count: {os.cpu_count()}")
        except Exception:
            pass

        return ("system_info.txt", "\n".join(lines) + "\n")

    # -- Health Reports --

    def _collect_health_reports(self):
        report_path = (
            Path.home() / ".config" / "webzfs" / "health_reports.json"
        )
        if not report_path.exists():
            return (
                "health_reports.json",
                json.dumps(
                    {"message": "No health reports found."}, indent=2
                )
                + "\n",
            )
        try:
            content = report_path.read_text(encoding="utf-8")
            # Validate it is JSON and re-format for readability
            data = json.loads(content)
            return ("health_reports.json", json.dumps(data, indent=2) + "\n")
        except Exception as exc:
            return (
                "health_reports.json",
                json.dumps({"error": str(exc)}, indent=2) + "\n",
            )

    # -- Audit Logs --

    def _collect_audit_logs(self):
        combined = []
        for category in LogCategory:
            log_path = audit_logger.log_dir / f"{category.value}.log"
            combined.append(f"=== {category.value} ===")
            if log_path.exists():
                try:
                    text = log_path.read_text(encoding="utf-8")
                    # Last 1000 lines
                    lines = text.splitlines()[-1000:]
                    combined.append("\n".join(lines))
                except Exception as exc:
                    combined.append(f"Error reading {log_path}: {exc}")
            else:
                combined.append("Log file does not exist.")
            combined.append("")
        return ("audit_logs.txt", "\n".join(combined) + "\n")
