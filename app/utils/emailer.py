# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Email utilities for sending alerts and digest notifications."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class EmailSender:
    """SMTP email sender with retry logic."""
    
    def __init__(self):
        """Initialize email sender with settings."""
        self.settings = get_settings()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send email with retry logic.
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.settings.require_smtp():
            logger.warning("SMTP not configured, skipping email")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.settings.SMTP_FROM_EMAIL
            msg['To'] = ', '.join(to_emails)
            
            # Add plain text part
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Connect to SMTP server
            with smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT) as server:
                if self.settings.SMTP_TLS:
                    server.starttls()
                
                if self.settings.SMTP_USERNAME and self.settings.SMTP_PASSWORD:
                    server.login(self.settings.SMTP_USERNAME, self.settings.SMTP_PASSWORD)
                
                # Send email
                server.send_message(msg, to_addrs=to_emails)
                
            logger.info(f"Email sent successfully to {len(to_emails)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise

def send_alert_email(
    alert_rule_name: str,
    post_title: str,
    post_content: str,
    channel_name: str,
    post_url: str,
    recipient_emails: List[str]
) -> bool:
    """
    Send an alert email for a matching post.
    
    Args:
        alert_rule_name: Name of the triggered alert rule
        post_title: Title of the post
        post_content: Content of the post (truncated)
        channel_name: Name of the Telegram channel
        post_url: URL to the original post
        recipient_emails: List of recipient email addresses
        
    Returns:
        True if email sent successfully
    """
    emailer = EmailSender()
    
    subject = f"News Alert: {alert_rule_name}"
    
    # Truncate content for email
    truncated_content = post_content[:500] + "..." if len(post_content) > 500 else post_content
    
    body = f"""
News Alert: {alert_rule_name}

Channel: {channel_name}
Title: {post_title}

Content:
{truncated_content}

View original post: {post_url}

---
This is an automated alert from the Telegram News Summarizer.
"""
    
    html_body = f"""
<html>
<body>
    <h2 style="color: #e74c3c;">News Alert: {alert_rule_name}</h2>
    
    <p><strong>Channel:</strong> {channel_name}</p>
    <p><strong>Title:</strong> {post_title}</p>
    
    <h3>Content:</h3>
    <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 10px 0;">
        {truncated_content.replace(chr(10), '<br>')}
    </div>
    
    <p><a href="{post_url}" style="color: #007bff; text-decoration: none;">View original post</a></p>
    
    <hr style="margin-top: 20px;">
    <p style="color: #6c757d; font-size: 12px;">
        This is an automated alert from the Telegram News Summarizer.
    </p>
</body>
</html>
"""
    
    return emailer.send_email(recipient_emails, subject, body, html_body)

def send_digest_email(
    digest_summary: str,
    post_count: int,
    language: str,
    recipient_emails: List[str]
) -> bool:
    """
    Send a digest email with summarized content.
    
    Args:
        digest_summary: LLM-generated summary
        post_count: Number of posts in the digest
        language: Target language of the summary
        recipient_emails: List of recipient email addresses
        
    Returns:
        True if email sent successfully
    """
    emailer = EmailSender()
    
    subject = f"Daily News Digest - {post_count} posts ({language.upper()})"
    
    body = f"""
Daily News Digest

Summary ({language.upper()}):
{digest_summary}

This digest includes {post_count} posts from the last hour.

---
This is an automated digest from the Telegram News Summarizer.
"""
    
    html_body = f"""
<html>
<body>
    <h2 style="color: #28a745;">Daily News Digest</h2>
    
    <div style="background-color: #d4edda; padding: 15px; border-left: 4px solid #28a745; margin: 10px 0;">
        <h3>Summary ({language.upper()}):</h3>
        <div style="white-space: pre-line; line-height: 1.6;">
{digest_summary}
        </div>
    </div>
    
    <p style="color: #6c757d;">
        This digest includes <strong>{post_count}</strong> posts from the last hour.
    </p>
    
    <hr style="margin-top: 20px;">
    <p style="color: #6c757d; font-size: 12px;">
        This is an automated digest from the Telegram News Summarizer.
    </p>
</body>
</html>
"""
    
    return emailer.send_email(recipient_emails, subject, body, html_body)
