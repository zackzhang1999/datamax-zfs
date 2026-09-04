"""Shell service for maintaining interactive shell sessions."""
import glob
import os
import subprocess
from datetime import datetime
from pathlib import Path

from core.exceptions import ProcessError


class ShellSession:
    """Maintains state for an interactive shell session."""
    
    # Cache for available system commands (shared across all instances)
    _command_cache: list[str] | None = None

    def __init__(self, initial_cwd: str = None):
        """Initialize a shell session with a working directory."""
        self.cwd = initial_cwd or os.getcwd()
        self.history: list[dict] = []

    def execute_command(self, command: str) -> tuple[str, str | None]:
        """
        Execute a command in the current working directory.
        
        Args:
            command: The command to execute
            
        Returns:
            Tuple of (output, error) where error is None if successful
        """
        command = command.strip()
        if not command:
            return "", None

        # Handle cd command specially to change working directory
        if command.startswith("cd "):
            return self._handle_cd(command[3:].strip())
        elif command == "cd":
            # cd with no args goes to home directory
            return self._handle_cd("~")

        # Execute the command in the current working directory
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
            )
            
            output = result.stdout
            if result.stderr:
                output += result.stderr
            
            # Record in history
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "command": command,
                "cwd": self.cwd,
                "output": output,
                "returncode": result.returncode,
            })
            
            if result.returncode != 0:
                return output, f"命令退出，状态码 {result.returncode}"
            
            return output, None
            
        except subprocess.TimeoutExpired:
            error_msg = "命令执行超过 30 秒，已超时"
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "command": command,
                "cwd": self.cwd,
                "output": error_msg,
                "returncode": -1,
            })
            return "", error_msg
        except Exception as exc:
            error_msg = f"命令执行失败：{str(exc)}"
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "command": command,
                "cwd": self.cwd,
                "output": error_msg,
                "returncode": -1,
            })
            return "", error_msg

    def _handle_cd(self, path: str) -> tuple[str, str | None]:
        """
        Handle the cd (change directory) command.
        
        Args:
            path: The path to change to
            
        Returns:
            Tuple of (output, error) where error is None if successful
        """
        if not path or path == "~":
            # Go to home directory
            path = str(Path.home())
        elif path.startswith("~/"):
            # Expand home directory
            path = str(Path.home() / path[2:])
        elif not os.path.isabs(path):
            # Make relative path absolute based on current directory
            path = os.path.join(self.cwd, path)
        
        # Normalize the path
        path = os.path.normpath(path)
        
        # Check if directory exists
        if not os.path.exists(path):
            error_msg = f"cd: {path}: 没有此文件或目录"
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "command": f"cd {path}",
                "cwd": self.cwd,
                "output": error_msg,
                "returncode": 1,
            })
            return "", error_msg
        
        if not os.path.isdir(path):
            error_msg = f"cd: {path}: 不是目录"
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "command": f"cd {path}",
                "cwd": self.cwd,
                "output": error_msg,
                "returncode": 1,
            })
            return "", error_msg
        
        # Update current working directory
        old_cwd = self.cwd
        self.cwd = path
        
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "command": f"cd {path}",
            "cwd": old_cwd,
            "output": f"已切换到目录 {self.cwd}",
            "returncode": 0,
        })
        
        return f"已切换到目录 {self.cwd}", None

    def get_history_text(self) -> str:
        """
        Get the command history as formatted text.
        
        Returns:
            Formatted text representation of command history
        """
        lines = [
            "=" * 80,
            "SHELL 命令历史",
            f"生成时间：{datetime.now().isoformat()}",
            "=" * 80,
            "",
        ]
        
        for entry in self.history:
            lines.append(f"[{entry['timestamp']}] {entry['cwd']}")
            lines.append(f"# {entry['command']}")
            if entry['output']:
                lines.append(entry['output'])
            lines.append(f"退出码：{entry['returncode']}")
            lines.append("-" * 80)
            lines.append("")
        
        return "\n".join(lines)

    def tab_complete(self, partial_command: str) -> list[str]:
        """
        Provide tab completion suggestions for a partial command.
        
        Args:
            partial_command: The partial command to complete
            
        Returns:
            List of completion suggestions
        """
        partial_command = partial_command.strip()
        
        # Split command into parts
        parts = partial_command.split()
        
        if not parts:
            return []
        
        # If only one part or completing the first word, suggest commands
        if len(parts) == 1 and not partial_command.endswith(' '):
            return self._complete_command(parts[0])
        
        # Otherwise, complete file paths
        # Get the last part that might be a path
        if partial_command.endswith(' '):
            # Starting a new argument
            path_to_complete = ""
        else:
            # Completing current argument
            path_to_complete = parts[-1]
        
        return self._complete_path(path_to_complete)
    
    def _complete_command(self, partial: str) -> list[str]:
        """
        Complete command names from system binary directories.
        
        Args:
            partial: Partial command name
            
        Returns:
            List of matching commands
        """
        # Build command cache if not already built
        if ShellSession._command_cache is None:
            ShellSession._command_cache = self._build_command_cache()
        
        # Filter commands that match the partial input
        matching_commands = [
            cmd for cmd in ShellSession._command_cache 
            if cmd.startswith(partial)
        ]
        
        # Limit to 20 suggestions and sort
        return sorted(matching_commands[:20])
    
    def _build_command_cache(self) -> list[str]:
        """
        Build a cache of available commands from system binary directories.
        
        Returns:
            List of available command names
        """
        commands = set()
        
        # Directories to scan for binaries
        binary_dirs = ['/bin', '/sbin', '/usr/bin', '/usr/sbin', '/usr/local/sbin', '/usr/local/bin']
        
        for directory in binary_dirs:
            try:
                if os.path.isdir(directory):
                    # List all files in the directory
                    for filename in os.listdir(directory):
                        filepath = os.path.join(directory, filename)
                        # Check if it's a file and executable
                        if os.path.isfile(filepath) and os.access(filepath, os.X_OK):
                            commands.add(filename)
            except (PermissionError, OSError):
                # Skip directories we can't read
                continue
        
        return list(commands)
    
    def _complete_path(self, partial: str) -> list[str]:
        """
        Complete file and directory paths.
        
        Args:
            partial: Partial path
            
        Returns:
            List of matching paths
        """
        try:
            # Handle home directory expansion
            if partial.startswith('~'):
                partial = os.path.expanduser(partial)
            
            # If path is relative, make it relative to current directory
            if not os.path.isabs(partial):
                partial = os.path.join(self.cwd, partial)
            
            # Add wildcard for globbing
            pattern = partial + '*'
            
            # Get matches
            matches = glob.glob(pattern)
            
            # Convert back to relative paths if original was relative
            results = []
            for match in matches[:20]:  # Limit to 20 results
                # Get the display name
                if match.startswith(self.cwd):
                    # Make relative to current directory
                    display = os.path.relpath(match, self.cwd)
                else:
                    display = match
                
                # Add trailing slash for directories
                if os.path.isdir(match):
                    display += '/'
                
                results.append(display)
            
            return sorted(results)
        except Exception:
            return []


# Global dictionary to store sessions per user
# In production, this should use Redis or a database
_sessions: dict[str, ShellSession] = {}


def get_shell_session(session_id: str) -> ShellSession:
    """
    Get or create a shell session for the given session ID.
    
    Args:
        session_id: Unique identifier for the session (e.g., username)
        
    Returns:
        ShellSession instance
    """
    if session_id not in _sessions:
        _sessions[session_id] = ShellSession()
    return _sessions[session_id]


def clear_shell_session(session_id: str) -> None:
    """
    Clear the shell session for the given session ID.
    
    Args:
        session_id: Unique identifier for the session
    """
    if session_id in _sessions:
        del _sessions[session_id]
