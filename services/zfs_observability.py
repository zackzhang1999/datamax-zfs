"""
ZFS Observability Service
Handles retrieval and parsing of ZFS logs, events, and history
"""
import subprocess
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from services.utils import is_freebsd, is_netbsd, run_zfs_command
from config.settings import Settings


class ZFSObservabilityService:
    """Service for ZFS observability, logs, and events"""
    
    def __init__(self):
        """Initialize the ZFS Observability Service with settings"""
        self.settings = Settings()
        self.timeouts = self.settings.ZPOOL_TIMEOUTS
    
    def get_pool_history(
        self,
        pool_name: Optional[str] = None,
        limit: int = 1000,
        since: Optional[datetime] = None,
        internal: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get ZFS pool command history
        
        Args:
            pool_name: Optional pool name to filter by
            limit: Maximum number of entries to return
            since: Optional datetime to filter entries after
            internal: Include internal events
            
        Returns:
            List of parsed history entries
        """
        timeout = self.timeouts.get('history', self.timeouts['default'])
        try:
            cmd = ['zpool', 'history', '-l']
            if internal:
                cmd.append('-i')
            if pool_name:
                cmd.append(pool_name)
            
            result = run_zfs_command(
                cmd,
                check=True,
                timeout=timeout
            )
            
            history = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                # Parse history line
                # Format: 2023-11-16.12:34:56 zfs create tank/dataset [user root on apollo]
                entry = self._parse_history_line(line)
                if entry:
                    # Filter by since date if provided
                    if since and entry.get('timestamp'):
                        try:
                            entry_time = datetime.fromisoformat(entry['timestamp'])
                            if entry_time < since:
                                continue
                        except:
                            pass
                    
                    history.append(entry)
            
            # Return last 'limit' entries
            return history[-limit:]
        
        except subprocess.TimeoutExpired:
            raise Exception(f"zpool history 命令在 {timeout} 秒后超时。历史记录可能非常大。")
        except subprocess.CalledProcessError as e:
            raise Exception(f"获取存储池历史记录失败：{e.stderr}")
    
    def get_pool_events(
        self,
        pool_name: Optional[str] = None,
        verbose: bool = False,
        follow: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get ZFS pool events
        
        Args:
            pool_name: Optional pool name to filter by
            verbose: Include verbose event details
            follow: Follow mode (not implemented for now)
            
        Returns:
            List of parsed event entries
        """
        # NetBSD ZFS does not support the 'events' subcommand
        if is_netbsd():
            return []
        
        timeout = self.timeouts.get('events', self.timeouts['default'])
        try:
            cmd = ['zpool', 'events']
            if verbose:
                cmd.append('-v')
            if pool_name:
                cmd.append(pool_name)
            
            result = run_zfs_command(
                cmd,
                check=True,
                timeout=timeout
            )
            
            events = []
            
            if verbose:
                # In verbose mode, group lines together per event
                lines = result.stdout.strip().split('\n')
                current_event_lines = []
                
                for line in lines:
                    if not line or line.startswith('TIME'):
                        continue
                    
                    # Check if this is a header line (starts with timestamp, not indented)
                    if line and not line[0].isspace():
                        # Save previous event if exists
                        if current_event_lines:
                            event = self._parse_verbose_event(current_event_lines)
                            if event:
                                events.append(event)
                        # Start new event
                        current_event_lines = [line]
                    else:
                        # This is a detail line, add to current event
                        if current_event_lines:
                            current_event_lines.append(line)
                
                # Don't forget the last event
                if current_event_lines:
                    event = self._parse_verbose_event(current_event_lines)
                    if event:
                        events.append(event)
            else:
                # Normal mode: one line per event
                for line in result.stdout.strip().split('\n'):
                    if not line or line.startswith('TIME'):
                        continue
                    
                    event = self._parse_event_line(line, verbose)
                    if event:
                        events.append(event)
            
            return events
        
        except subprocess.TimeoutExpired:
            raise Exception(f"zpool events 命令在 {timeout} 秒后超时。系统可能无响应。")
        except subprocess.CalledProcessError as e:
            raise Exception(f"获取存储池事件失败：{e.stderr}")
    
    def clear_pool_events(self, pool_name: Optional[str] = None) -> None:
        """
        Clear ZFS pool events
        
        Args:
            pool_name: Optional pool name, clears all if not provided
        """
        # NetBSD ZFS does not support the 'events' subcommand
        if is_netbsd():
            return
        
        timeout = self.timeouts.get('events', self.timeouts['default'])
        try:
            cmd = ['zpool', 'events', '-c']
            if pool_name:
                cmd.append(pool_name)
            
            run_zfs_command(
                cmd,
                check=True,
                timeout=timeout
            )
        except subprocess.TimeoutExpired:
            raise Exception(f"zpool 清除事件命令在 {timeout} 秒后超时。系统可能无响应。")
        except subprocess.CalledProcessError as e:
            raise Exception(f"清除存储池事件失败：{e.stderr}")
    
    def get_kernel_debug_log(
        self,
        lines: int = 1000,
        filter_pattern: Optional[str] = None
    ) -> List[str]:
        """
        Get ZFS kernel debug messages
        
        Args:
            lines: Maximum number of lines to return
            filter_pattern: Optional regex pattern to filter messages
            
        Returns:
            List of log lines
        """
        # FreeBSD/NetBSD use sysctl for debug messages
        if is_freebsd() or is_netbsd():
            return self._get_kernel_debug_log_sysctl(lines, filter_pattern)
        else:
            return self._get_kernel_debug_log_linux(lines, filter_pattern)
    
    def _get_kernel_debug_log_linux(
        self,
        lines: int = 1000,
        filter_pattern: Optional[str] = None
    ) -> List[str]:
        """
        Get ZFS kernel debug messages from Linux /proc filesystem
        
        Args:
            lines: Maximum number of lines to return
            filter_pattern: Optional regex pattern to filter messages
            
        Returns:
            List of log lines
        """
        try:
            dbgmsg_path = '/proc/spl/kstat/zfs/dbgmsg'
            
            # Check if file exists first
            if not Path(dbgmsg_path).exists():
                return ["调试日志不可用（缺少 /proc/spl/kstat/zfs/dbgmsg）"]
            
            # Use sudo cat to read the privileged file
            result = subprocess.run(
                ['sudo', 'cat', dbgmsg_path],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                # If sudo fails, try direct read as fallback (might work if already root)
                try:
                    with open(dbgmsg_path, 'r') as f:
                        log_lines = f.readlines()
                except PermissionError:
                    return [f"读取 {dbgmsg_path} 的权限被拒绝",
                            "",
                            "在 Linux 上修复方法，请将以下内容添加到 sudoers：",
                            "  webzfs ALL=(ALL) NOPASSWD: /usr/bin/cat /proc/spl/kstat/zfs/dbgmsg"]
            else:
                log_lines = result.stdout.split('\n')
            
            # Filter if pattern provided
            if filter_pattern:
                pattern = re.compile(filter_pattern, re.IGNORECASE)
                log_lines = [line for line in log_lines if pattern.search(line)]
            
            # Return last N lines
            return [line.strip() for line in log_lines[-lines:] if line.strip()]
            
        except Exception as e:
            return [f"读取调试日志出错：{str(e)}"]
    
    def _get_kernel_debug_log_sysctl(
        self,
        lines: int = 1000,
        filter_pattern: Optional[str] = None
    ) -> List[str]:
        """
        Get ZFS kernel debug messages from sysctl (FreeBSD/NetBSD)
        
        Args:
            lines: Maximum number of lines to return
            filter_pattern: Optional regex pattern to filter messages
            
        Returns:
            List of log lines
        """
        try:
            # FreeBSD/NetBSD use sysctl for ZFS debug messages
            # Try kstat.zfs.misc.dbgmsg first (more common)
            result = subprocess.run(
                ['sysctl', '-n', 'kstat.zfs.misc.dbgmsg'],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0 or not result.stdout.strip():
                # Try alternative location vfs.zfs.dbgmsg
                result = subprocess.run(
                    ['sysctl', '-n', 'vfs.zfs.dbgmsg'],
                    capture_output=True,
                    text=True,
                    check=False
                )
            
            if result.returncode != 0 or not result.stdout.strip():
                # Debug messages may not be enabled
                return ["调试日志不可用（无法访问 sysctl kstat.zfs.misc.dbgmsg）",
                        "",
                        "要在 FreeBSD 上启用 ZFS 调试消息，可能需要：",
                        "  1. 执行：sysctl vfs.zfs.dbgmsg_enable=1",
                        "  2. 或检查内核是否编译了 ZFS 调试选项"]
            
            # Parse the output - each line is a debug message
            log_lines = result.stdout.strip().split('\n')
            
            # Filter if pattern provided
            if filter_pattern:
                pattern = re.compile(filter_pattern, re.IGNORECASE)
                log_lines = [line for line in log_lines if pattern.search(line)]
            
            # Return last N lines
            return [line.strip() for line in log_lines[-lines:] if line.strip()]
            
        except Exception as e:
            return [f"通过 sysctl 读取调试日志出错：{str(e)}"]
    
    def get_syslog_zfs(
        self,
        lines: int = 1000,
        since: Optional[datetime] = None,
        severity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get ZFS-related syslog entries
        
        Args:
            lines: Maximum number of entries to return
            since: Optional datetime to filter entries after
            severity: Optional severity filter (error, warning, info)
            
        Returns:
            List of syslog entries
        """
        if is_freebsd() or is_netbsd():
            # BSD uses syslog - grep /var/log/messages
            return self._read_bsd_syslog(lines, since, severity)

        # Linux: walk through possible sources and grep for zfs/zpool.
        # We try unprivileged journalctl, then sudo -n journalctl (in
        # case the webzfs user is not in systemd-journal but does have
        # NOPASSWD sudo for journalctl), then plain text syslog files
        # (with sudo as a second pass), then dmesg. Each step records
        # any stderr it produces so the caller can surface a real
        # error if everything fails.
        zfs_lines: List[Dict[str, Any]] = []
        attempt_errors: List[str] = []

        priority_map = {
            'error': 'err',
            'warning': 'warning',
            'info': 'info',
        }

        def build_journalctl_cmd(prefix: List[str]) -> List[str]:
            cmd = list(prefix) + ['journalctl', '-n', str(lines), '--no-pager']
            if since:
                cmd.extend(['--since', since.isoformat()])
            if severity and severity.lower() in priority_map:
                cmd.extend(['-p', priority_map[severity.lower()]])
            return cmd

        for prefix in ([], ['sudo', '-n']):
            try:
                result = subprocess.run(
                    build_journalctl_cmd(prefix),
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except FileNotFoundError:
                continue

            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.split('\n'):
                    low = line.lower()
                    if 'zfs' in low or 'zpool' in low:
                        zfs_lines.append({'message': line.strip()})
                if zfs_lines:
                    return zfs_lines
                # journalctl worked but no ZFS lines found; do not
                # fall through to syslog files in that case
                return [{'message': 'journalctl 输出中未找到 ZFS 消息'}]

            err = (result.stderr or '').strip()
            if err:
                label = 'sudo journalctl' if prefix else 'journalctl'
                attempt_errors.append(f'{label}: {err.splitlines()[0]}')

        # Plain text syslog files (Debian/Ubuntu and old RHEL).
        # Try unprivileged then sudo -n cat for each path.
        for path in ('/var/log/syslog', '/var/log/messages'):
            for use_sudo in (False, True):
                argv = (
                    ['sudo', '-n', 'tail', '-n', str(lines * 5), path]
                    if use_sudo
                    else ['tail', '-n', str(lines * 5), path]
                )
                try:
                    result = subprocess.run(
                        argv,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                except FileNotFoundError:
                    break
                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.split('\n'):
                        low = line.lower()
                        if 'zfs' in low or 'zpool' in low:
                            zfs_lines.append({'message': line.strip()})
                    if zfs_lines:
                        return zfs_lines[-lines:]
                    # File readable but no ZFS lines; stop searching
                    return [{'message': f'{path} 中未找到 ZFS 消息'}]
                err = (result.stderr or '').strip()
                if err and 'No such file' not in err:
                    label = f'sudo tail {path}' if use_sudo else f'tail {path}'
                    attempt_errors.append(f'{label}: {err.splitlines()[0]}')

        # Last resort: dmesg ring buffer
        fallback = self._fallback_syslog_read(lines)
        if fallback and fallback[0].get('message') not in (
            '系统日志不可用',
            '读取系统日志出错',
        ):
            return fallback

        if attempt_errors:
            return [
                {'message': '系统日志不可用。已尝试：'},
            ] + [{'message': '  ' + msg} for msg in attempt_errors] + [
                {'message': ''},
                {'message': '请将 journalctl 加入 webzfs 的 sudoers，或将 webzfs 用户加入 systemd-journal 组：'},
                {'message': '  sudo usermod -aG systemd-journal webzfs'},
            ]
        return fallback
    
    def get_arc_summary(self) -> Dict[str, Any]:
        """
        Get ARC (Adaptive Replacement Cache) statistics
        
        Returns:
            Dictionary with ARC stats
        """
        # FreeBSD/NetBSD use sysctl for ARC stats
        if is_freebsd() or is_netbsd():
            return self._get_arc_summary_sysctl()
        else:
            return self._get_arc_summary_linux()
    
    def _get_arc_summary_linux(self) -> Dict[str, Any]:
        """Get ARC stats from Linux /proc filesystem"""
        try:
            arcstats_path = Path('/proc/spl/kstat/zfs/arcstats')
            
            if not arcstats_path.exists():
                return {'error': 'ARC 统计信息不可用'}
            
            stats = {}
            with open(arcstats_path, 'r') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    
                    parts = line.split()
                    if len(parts) >= 3:
                        name = parts[0]
                        value = parts[2]
                        try:
                            stats[name] = int(value)
                        except ValueError:
                            stats[name] = value
            
            # Calculate derived stats
            if 'hits' in stats and 'misses' in stats:
                total = stats['hits'] + stats['misses']
                if total > 0:
                    stats['hit_rate'] = (stats['hits'] / total) * 100
            
            # Format sizes
            if 'size' in stats:
                stats['size_human'] = self._format_bytes(stats['size'])
            if 'c_max' in stats:
                stats['c_max_human'] = self._format_bytes(stats['c_max'])
            
            self._add_l2arc_summary(stats)
            return stats
            
        except Exception as e:
            return {'error': f'读取 ARC 统计信息失败：{str(e)}'}
    
    def _get_arc_summary_sysctl(self) -> Dict[str, Any]:
        """
        Get ARC stats using sysctl (for BSD systems)
        
        Returns:
            Dictionary with ARC stats
        """
        try:
            # Get all ZFS ARC-related sysctl values
            result = subprocess.run(
                ['sysctl', 'kstat.zfs.misc.arcstats'],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                return {'error': '读取 ARC 统计信息的 sysctl 失败'}
            
            stats = {}
            
            for line in result.stdout.split('\n'):
                if not line.strip():
                    continue
                
                # Parse sysctl output: name: value (FreeBSD) or name=value (NetBSD)
                if ': ' in line:
                    name, value = line.split(': ', 1)
                elif '=' in line:
                    name, value = line.split('=', 1)
                else:
                    continue
                
                name = name.strip()
                value = value.strip()
                
                # Extract just the stat name (last part after dots)
                # kstat.zfs.misc.arcstats.hits -> hits
                stat_name = name.split('.')[-1]
                
                try:
                    stats[stat_name] = int(value)
                except ValueError:
                    stats[stat_name] = value
            
            if not stats:
                return {'error': '无法通过 sysctl 获取 ARC 统计信息'}
            
            # Calculate derived stats
            if 'hits' in stats and 'misses' in stats:
                total = stats['hits'] + stats['misses']
                if total > 0:
                    stats['hit_rate'] = (stats['hits'] / total) * 100
            
            # Format sizes
            if 'size' in stats:
                stats['size_human'] = self._format_bytes(stats['size'])
            if 'c_max' in stats:
                stats['c_max_human'] = self._format_bytes(stats['c_max'])
            
            self._add_l2arc_summary(stats)
            return stats
            
        except Exception as e:
            return {'error': f'读取 ARC 统计信息失败：{str(e)}'}

    def _add_l2arc_summary(self, stats: Dict[str, Any]) -> None:
        """Add L2ARC (SSD cache) derived statistics to a parsed arcstats dict."""
        hits = stats.get('l2_hits', 0) or 0
        misses = stats.get('l2_misses', 0) or 0
        try:
            hits = int(hits)
            misses = int(misses)
        except (TypeError, ValueError):
            hits = 0
            misses = 0

        total = hits + misses
        if total > 0:
            stats['l2_hit_rate'] = round((hits / total) * 100, 2)
            stats['l2_miss_rate'] = round((misses / total) * 100, 2)
        else:
            stats['l2_hit_rate'] = 0
            stats['l2_miss_rate'] = 0

        def first_nonzero(*keys: str) -> int:
            for key in keys:
                value = stats.get(key)
                if value is None:
                    continue
                try:
                    parsed = int(value)
                except (TypeError, ValueError):
                    continue
                if parsed > 0:
                    return parsed
            return 0

        # On some kernels l2_size/l2_asize stay zero while the persistent
        # L2ARC rebuild counters hold the real footprint, so fall back to
        # those before deciding whether an L2ARC is present.
        l2arc_counters = [
            first_nonzero('l2_size', 'l2_rebuild_size'),
            first_nonzero('l2_asize', 'l2_rebuild_asize'),
            hits,
            misses,
            int(stats.get('l2_feeds') or 0),
        ]
        stats['l2arc_active'] = sum(l2arc_counters) > 0

        stats['l2_size_human'] = self._format_bytes(
            first_nonzero('l2_size', 'l2_rebuild_size'),
        )
        stats['l2_asize_human'] = self._format_bytes(
            first_nonzero('l2_asize', 'l2_rebuild_asize'),
        )
        stats['l2_hdr_size_human'] = self._format_bytes(
            first_nonzero('l2_hdr_size'),
        )

        byte_fields = {
            'l2_read_bytes': 'l2_read_bytes_human',
            'l2_write_bytes': 'l2_write_bytes_human',
        }
        for source, target in byte_fields.items():
            value = stats.get(source)
            if isinstance(value, int):
                stats[target] = self._format_bytes(value)
            elif value is not None:
                try:
                    stats[target] = self._format_bytes(int(value))
                except (TypeError, ValueError):
                    stats[target] = 'N/A'

        count_fields = {
            'l2_hits': 'l2_hits_human',
            'l2_misses': 'l2_misses_human',
            'l2_feeds': 'l2_feeds_human',
            'l2_writes_sent': 'l2_writes_sent_human',
        }
        for source, target in count_fields.items():
            value = stats.get(source)
            if value is None:
                stats[target] = '0'
                continue
            try:
                stats[target] = f"{int(value):,}"
            except (TypeError, ValueError):
                stats[target] = str(value)
    
    def get_zfs_module_parameters(self) -> Dict[str, Any]:
        """
        Get current ZFS kernel module parameters
        
        Returns:
            Dictionary of parameter names and values
        """
        try:
            params_path = Path('/sys/module/zfs/parameters')
            
            if not params_path.exists():
                return {'error': 'ZFS 模块参数不可用'}
            
            parameters = {}
            for param_file in params_path.iterdir():
                if param_file.is_file():
                    try:
                        with open(param_file, 'r') as f:
                            value = f.read().strip()
                            parameters[param_file.name] = value
                    except:
                        parameters[param_file.name] = '<unreadable>'
            
            return parameters
            
        except Exception as e:
            return {'error': f'读取模块参数失败：{str(e)}'}
    
    def search_logs(
        self,
        query: str,
        source: str = "all",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search across all ZFS logs with a query string
        
        Args:
            query: Search query
            source: Log source (all, pool_history, events, kernel, syslog)
            limit: Maximum number of results
            
        Returns:
            List of matching log entries
        """
        results = []
        query_lower = query.lower()
        
        try:
            if source in ['all', 'pool_history']:
                history = self.get_pool_history(limit=limit)
                for entry in history:
                    if query_lower in str(entry).lower():
                        entry['source'] = 'pool_history'
                        results.append(entry)
            
            if source in ['all', 'events']:
                events = self.get_pool_events()
                for entry in events:
                    if query_lower in str(entry).lower():
                        entry['source'] = 'events'
                        results.append(entry)
            
            if source in ['all', 'kernel']:
                kernel_log = self.get_kernel_debug_log(lines=limit)
                for line in kernel_log:
                    if query_lower in line.lower():
                        results.append({
                            'source': 'kernel',
                            'message': line
                        })
            
            if source in ['all', 'syslog']:
                syslog = self.get_syslog_zfs(lines=limit)
                for entry in syslog:
                    if query_lower in str(entry).lower():
                        entry['source'] = 'syslog'
                        results.append(entry)
            
            return results[:limit]
            
        except Exception as e:
            return [{'error': f'搜索失败：{str(e)}'}]
    
    # Private helper methods
    
    def _parse_history_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a zpool history line"""
        try:
            # Skip header lines
            if line.startswith('History for'):
                return None
                
            # Format: 2023-11-16.12:34:56 full command here [user=root on hostname]
            # Split on first space to get timestamp
            parts = line.split(None, 1)
            if len(parts) < 2:
                return None
            
            timestamp_str = parts[0]
            rest = parts[1]
            
            # Extract user info if present (in brackets at end)
            command_line = rest
            user = None
            host = None
            
            if '[' in rest and ']' in rest:
                bracket_start = rest.rfind('[')
                command_line = rest[:bracket_start].strip()
                user_info = rest[bracket_start+1:rest.rfind(']')]
                
                # Parse user info like "user=root on hostname" or "user 0 on apollo:linux"
                if 'user' in user_info:
                    user_parts = user_info.split()
                    for i, part in enumerate(user_parts):
                        if part == 'user' or part.startswith('user='):
                            if part.startswith('user='):
                                user = part.split('=')[1]
                            elif i + 1 < len(user_parts):
                                user = user_parts[i + 1]
                        if part == 'on' and i + 1 < len(user_parts):
                            host = user_parts[i + 1]
            
            return {
                'timestamp': timestamp_str.replace('.', ' '),
                'command': command_line,
                'user': user,
                'host': host,
                'raw': line
            }
        except Exception as e:
            # Return the raw line if parsing fails
            return {'raw': line, 'command': line, 'timestamp': '', 'user': None, 'host': None}
    
    def _parse_event_line(self, line: str, verbose: bool) -> Optional[Dict[str, Any]]:
        """Parse a zpool events line"""
        try:
            # zpool events format: TIME (4 parts: month day year time) CLASS [details]
            # Example: Jan 13 2026 20:39:02.026667341 sysevent.fs.zfs.history_event
            parts = line.split(None, 4)  # Split into 5 parts max
            if len(parts) < 5:
                return None
            
            # First 4 parts are the timestamp
            time_str = f"{parts[0]} {parts[1]} {parts[2]} {parts[3]}"
            event_class = parts[4]
            
            return {
                'time': time_str,
                'class': event_class,
                'details': '',  # No additional details in non-verbose mode
                'raw': line
            }
        except:
            return {'raw': line}
    
    def _parse_verbose_event(self, lines: List[str]) -> Optional[Dict[str, Any]]:
        """Parse a verbose event with multiple lines"""
        try:
            if not lines:
                return None
            
            # First line is the header with timestamp and class
            header_line = lines[0]
            parts = header_line.split(None, 4)
            if len(parts) < 5:
                return {'raw': '\n'.join(lines)}
            
            # First 4 parts are the timestamp
            time_str = f"{parts[0]} {parts[1]} {parts[2]} {parts[3]}"
            event_class = parts[4]
            
            # Combine all lines for raw output
            raw_output = '\n'.join(lines)
            
            return {
                'time': time_str,
                'class': event_class,
                'raw': raw_output
            }
        except:
            return {'raw': '\n'.join(lines) if lines else ''}
    
    def _read_bsd_syslog(
        self,
        lines: int,
        since: Optional[datetime] = None,
        severity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """BSD-specific syslog reading from /var/log/messages"""
        try:
            # Read from /var/log/messages and filter for ZFS
            result = subprocess.run(
                ['sh', '-c', f'grep -i "zfs\\|zpool" /var/log/messages | tail -n {lines}'],
                capture_output=True,
                text=True,
                check=False
            )
            
            zfs_lines = []
            for line in result.stdout.split('\n'):
                if line.strip():
                    zfs_lines.append({'message': line.strip()})
            
            return zfs_lines if zfs_lines else [{'message': '未找到 ZFS 消息'}]
            
        except Exception as e:
            return [{'message': f'读取系统日志出错：{str(e)}'}]
    
    def _fallback_syslog_read(self, lines: int) -> List[Dict[str, Any]]:
        """Fallback method to read syslog without journalctl"""
        try:
            # Try dmesg (without -T flag on BSD systems)
            if is_freebsd() or is_netbsd():
                # BSD dmesg doesn't support -T flag
                result = subprocess.run(
                    ['dmesg'],
                    capture_output=True,
                    text=True,
                    check=False
                )
            else:
                # Linux dmesg with timestamps (default)
                result = subprocess.run(
                    ['dmesg', '-T'],
                    capture_output=True,
                    text=True,
                    check=False
                )
            
            if result.returncode == 0:
                zfs_lines = []
                for line in result.stdout.split('\n')[-lines:]:
                    if 'zfs' in line.lower() or 'zpool' in line.lower():
                        zfs_lines.append({'message': line.strip()})
                return zfs_lines
            
            return [{'message': '系统日志不可用'}]
            
        except:
            return [{'message': '读取系统日志出错'}]
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes to human-readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} PB"
