"""
Email Notification Service
Handles sending email notifications for replication job failures and other events
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from datetime import datetime
import os


class EmailNotificationService:
    """Service for sending email notifications"""
    
    def __init__(self):
        """Initialize email notification service with settings from environment"""
        self.smtp_enabled = os.getenv('SMTP_ENABLED', 'false').lower() == 'true'
        self.smtp_host = os.getenv('SMTP_HOST', 'localhost')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.smtp_use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
        self.smtp_from_address = os.getenv('SMTP_FROM_ADDRESS', 'webzfs@localhost')
        self.notification_recipients = os.getenv('NOTIFICATION_RECIPIENTS', '').split(',')
        # Filter out empty strings from recipients list
        self.notification_recipients = [r.strip() for r in self.notification_recipients if r.strip()]
    
    def is_configured(self) -> bool:
        """
        Check if email notifications are properly configured
        
        Returns:
            bool: True if SMTP is enabled and configured
        """
        return (self.smtp_enabled and 
                bool(self.smtp_host) and 
                bool(self.notification_recipients))
    
    def send_job_failure_notification(
        self,
        job_name: str,
        source_dataset: str,
        target_dataset: str,
        error_message: str,
        execution_id: int,
        duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Send email notification for job failure
        
        Args:
            job_name: Name of the replication job
            source_dataset: Source dataset
            target_dataset: Target dataset
            error_message: Error message from failure
            execution_id: Execution ID
            duration: Duration in seconds
            
        Returns:
            Dict with status and details
        """
        if not self.is_configured():
            return {
                'status': 'skipped',
                'message': '未配置电子邮件通知'
            }
        
        subject = f"ZFS 数据复制失败：{job_name}"
        
        body = self._format_failure_email(
            job_name=job_name,
            source_dataset=source_dataset,
            target_dataset=target_dataset,
            error_message=error_message,
            execution_id=execution_id,
            duration=duration
        )
        
        return self._send_email(subject, body, 'failure')
    
    def send_job_success_notification(
        self,
        job_name: str,
        source_dataset: str,
        target_dataset: str,
        execution_id: int,
        bytes_transferred: int,
        duration: float
    ) -> Dict[str, Any]:
        """
        Send email notification for job success (optional, only if enabled)
        
        Args:
            job_name: Name of the replication job
            source_dataset: Source dataset
            target_dataset: Target dataset
            execution_id: Execution ID
            bytes_transferred: Bytes transferred
            duration: Duration in seconds
            
        Returns:
            Dict with status and details
        """
        # Only send success notifications if explicitly enabled
        if not os.getenv('SMTP_NOTIFY_ON_SUCCESS', 'false').lower() == 'true':
            return {
                'status': 'skipped',
                'message': '未启用成功通知'
            }
        
        if not self.is_configured():
            return {
                'status': 'skipped',
                'message': '未配置电子邮件通知'
            }
        
        subject = f"ZFS 数据复制成功：{job_name}"
        
        body = self._format_success_email(
            job_name=job_name,
            source_dataset=source_dataset,
            target_dataset=target_dataset,
            execution_id=execution_id,
            bytes_transferred=bytes_transferred,
            duration=duration
        )
        
        return self._send_email(subject, body, 'success')
    
    def test_configuration(self) -> Dict[str, Any]:
        """
        Test email configuration by sending a test email
        
        Returns:
            Dict with status and details
        """
        if not self.is_configured():
            return {
                'status': 'failure',
                'message': '未配置电子邮件通知'
            }
        
        subject = "ZFS Web UI - 电子邮件测试"
        body = """这是一封来自 ZFS Web UI 的测试邮件。

如果您收到了这封邮件，说明您的电子邮件通知设置工作正常。

配置信息：
- SMTP 主机：{}
- SMTP 端口：{}
- 发件地址：{}
- 收件人：{}

发送时间：{}
""".format(
            self.smtp_host,
            self.smtp_port,
            self.smtp_from_address,
            ', '.join(self.notification_recipients),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        return self._send_email(subject, body, 'test')
    
    def _format_failure_email(
        self,
        job_name: str,
        source_dataset: str,
        target_dataset: str,
        error_message: str,
        execution_id: int,
        duration: Optional[float]
    ) -> str:
        """Format failure notification email body"""
        duration_str = f"{duration:.2f} 秒" if duration else "未知"
        
        return f"""ZFS 数据复制任务失败

任务详情：
- 任务名称：{job_name}
- 源数据集：{source_dataset}
- 目标数据集：{target_dataset}
- 执行 ID：{execution_id}
- 耗时：{duration_str}
- 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

错误详情：
{error_message}

需要处理：
请排查此次失败原因并采取相应措施。您可以在 Web 界面中查看
详细日志和进度信息。

---
这是一封来自 ZFS Web UI 的自动邮件。
"""
    
    def _format_success_email(
        self,
        job_name: str,
        source_dataset: str,
        target_dataset: str,
        execution_id: int,
        bytes_transferred: int,
        duration: float
    ) -> str:
        """Format success notification email body"""
        return f"""ZFS 数据复制任务已成功完成

任务详情：
- 任务名称：{job_name}
- 源数据集：{source_dataset}
- 目标数据集：{target_dataset}
- 执行 ID：{execution_id}
- 传输数据量：{self._format_bytes(bytes_transferred)}
- 耗时：{duration:.2f} 秒
- 平均速度：{self._calculate_speed(bytes_transferred, duration)}
- 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

数据复制已成功完成。

---
这是一封来自 ZFS Web UI 的自动邮件。
"""
    
    def _send_email(
        self,
        subject: str,
        body: str,
        notification_type: str
    ) -> Dict[str, Any]:
        """
        Send email using SMTP
        
        Args:
            subject: Email subject
            body: Email body
            notification_type: Type of notification (failure/success/test)
            
        Returns:
            Dict with status and details
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.smtp_from_address
            msg['To'] = ', '.join(self.notification_recipients)
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to SMTP server
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            
            # Login if credentials provided
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            return {
                'status': 'sent',
                'message': f'邮件已成功发送给 {len(self.notification_recipients)} 位收件人',
                'recipients': self.notification_recipients
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'发送邮件失败：{str(e)}',
                'error': str(e)
            }
    
    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes to human-readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.2f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.2f} PB"
    
    def _calculate_speed(self, bytes_count: int, duration: float) -> str:
        """Calculate transfer speed"""
        if duration <= 0:
            return "N/A"
        
        bytes_per_sec = bytes_count / duration
        return f"{self._format_bytes(bytes_per_sec)}/s"
