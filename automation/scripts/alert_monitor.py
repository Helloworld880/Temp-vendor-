#!/usr/bin/env python3
"""
Report Scheduler for Vendor Dashboard
Automates generation and distribution of scheduled reports
"""

import os
import sys
import json
import logging
import schedule
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from email.mime.application import MimeApplication
import sqlite3
import pandas as pd

class ReportScheduler:
    def __init__(self, config_path: str = "config/report_config.json"):
        self.config = self.load_config(config_path)
        self.setup_logging()
        self.setup_database()
        self.setup_schedule()
        
    def load_config(self, config_path: str) -> Dict:
        """Load report configuration"""
        default_config = {
            "schedules": {
                "daily_performance": {
                    "enabled": True,
                    "schedule": "08:00",
                    "report_type": "performance",
                    "recipients": ["vendor_managers@company.com"],
                    "format": "pdf"
                },
                "weekly_summary": {
                    "enabled": True,
                    "schedule": "monday 09:00",
                    "report_type": "comprehensive",
                    "recipients": ["executive_team@company.com", "vendor_management@company.com"],
                    "format": "pdf"
                },
                "monthly_analytics": {
                    "enabled": True,
                    "schedule": "1 10:00",  # 1st of month at 10:00
                    "report_type": "analytics",
                    "recipients": ["analytics_team@company.com", "vendor_directors@company.com"],
                    "format": "excel"
                },
                "quarterly_review": {
                    "enabled": True,
                    "schedule": "0 0 1 */3 *",  # Every 3 months on 1st
                    "report_type": "quarterly",
                    "recipients": ["executive_committee@company.com"],
                    "format": "pdf"
                }
            },
            "email_settings": {
                "smtp_server": "smtp.company.com",
                "smtp_port": 587,
                "username": "reports@company.com",
                "password": "",
                "from_address": "Vendor Reports <reports@company.com>"
            },
            "report_settings": {
                "retention_days": 90,
                "storage_path": "reports/scheduled/",
                "include_executive_summary": True,
                "include_recommendations": True
            }
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
        except Exception as e:
            logging.warning(f"Could not load report config: {e}")
            
        return default_config
    
    def setup_logging(self):
        """Setup logging for report scheduling"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/report_scheduler.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_database(self):
        """Setup database connection"""
        self.db_path = "data/vendors.db"
        self.conn = sqlite3.connect(self.db_path)
    
    def setup_schedule(self):
        """Setup scheduled tasks"""
        try:
            # Clear existing schedules
            schedule.clear()
            
            # Setup schedules from config
            for schedule_name, schedule_config in self.config['schedules'].items():
                if schedule_config.get('enabled', False):
                    self.setup_scheduled_report(schedule_name, schedule_config)
            
            self.logger.info("Report schedules configured successfully")
            
        except Exception as e:
            self.logger.error(f"Error setting up schedules: {e}")
    
    def setup_scheduled_report(self, schedule_name: str, schedule_config: Dict):
        """Setup individual scheduled report"""
        try:
            schedule_time = schedule_config['schedule']
            report_type = schedule_config['report_type']
            
            # Map schedule patterns to schedule library
            if ':' in schedule_time and ' ' not in schedule_time:
                # Daily schedule (e.g., "08:00")
                schedule.every().day.at(schedule_time).do(
                    self.generate_scheduled_report, schedule_name, schedule_config
                ).tag(schedule_name)
                
            elif schedule_time.split(" ", 1)[0].lower() in {
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            }:
                # Weekly schedule (e.g., "monday 09:00")
                day, time_str = schedule_time.split(' ')
                getattr(schedule.every(), day.lower()).at(time_str).do(
                    self.generate_scheduled_report, schedule_name, schedule_config
                ).tag(schedule_name)
                
            elif schedule_time.startswith('1 ') or schedule_time.startswith('15 '):
                # Monthly schedule (e.g., "1 10:00")
                day, time_str = schedule_time.split(' ')
                schedule.every().month.at(time_str).do(
                    self.generate_scheduled_report, schedule_name, schedule_config
                ).tag(schedule_name)
                
            else:
                # Cron-like schedule (e.g., "0 0 1 */3 *")
                schedule.every().cron(schedule_time).do(
                    self.generate_scheduled_report, schedule_name, schedule_config
                ).tag(schedule_name)
            
            self.logger.info(f"Scheduled {schedule_name} report for {schedule_time}")
            
        except Exception as e:
            self.logger.error(f"Error setting up {schedule_name} schedule: {e}")
    
    def generate_scheduled_report(self, schedule_name: str, schedule_config: Dict):
        """Generate and distribute scheduled report"""
        try:
            self.logger.info(f"Generating scheduled report: {schedule_name}")
            
            report_type = schedule_config['report_type']
            report_format = schedule_config.get('format', 'pdf')
            recipients = schedule_config.get('recipients', [])
            
            # Generate report
            report_path = self.generate_report(report_type, report_format, schedule_name)
            
            if report_path and os.path.exists(report_path):
                # Send report via email
                email_sent = self.send_report_email(
                    recipients=recipients,
                    subject=f"Vendor {report_type.title()} Report - {datetime.now().strftime('%Y-%m-%d')}",
                    report_path=report_path,
                    report_type=report_type,
                    schedule_name=schedule_name
                )
                
                # Log report generation
                self.log_report_generation(
                    schedule_name=schedule_name,
                    report_type=report_type,
                    report_path=report_path,
                    recipients=recipients,
                    email_sent=email_sent,
                    success=True
                )
                
                self.logger.info(f"Successfully generated and distributed {schedule_name} report")
                
            else:
                self.logger.error(f"Failed to generate report for {schedule_name}")
                self.log_report_generation(
                    schedule_name=schedule_name,
                    report_type=report_type,
                    report_path=None,
                    recipients=recipients,
                    email_sent=False,
                    success=False,
                    error_message="Report generation failed"
                )
                
        except Exception as e:
            self.logger.error(f"Error generating scheduled report {schedule_name}: {e}")
            self.log_report_generation(
                schedule_name=schedule_name,
                report_type=schedule_config.get('report_type', 'unknown'),
                report_path=None,
                recipients=schedule_config.get('recipients', []),
                email_sent=False,
                success=False,
                error_message=str(e)
            )
    
    def generate_report(self, report_type: str, format_type: str, schedule_name: str) -> Optional[str]:
        """Generate specific type of report"""
        try:
            from enhancements.report_generator import ReportGenerator
            from core.database import DatabaseManager
            
            db_manager = DatabaseManager()
            report_generator = ReportGenerator(db_manager)
            
            report_path = None
            
            if report_type == "performance":
                report_path = report_generator.generate_performance_report(
                    vendor_ids=None, 
                    report_format=format_type
                )
                
            elif report_type == "comprehensive":
                report_path = report_generator.generate_comprehensive_report(
                    report_format=format_type
                )
                
            elif report_type == "analytics":
                # Generate analytics report with specific parameters
                vendors = db_manager.get_vendors()
                vendor_ids = [v['vendor_id'] for v in vendors]
                report_path = report_generator.generate_performance_report(
                    vendor_ids=vendor_ids,
                    report_format=format_type
                )
                
            elif report_type == "quarterly":
                # Generate quarterly review report
                from enhancements.benchmarking import Benchmarking
                benchmarking = Benchmarking(db_manager)
                benchmark_report = benchmarking.generate_benchmarking_report()
                
                # Save benchmark report
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                if format_type == 'pdf':
                    report_path = f"reports/quarterly_benchmark_{timestamp}.pdf"
                else:
                    report_path = f"reports/quarterly_benchmark_{timestamp}.xlsx"
                
                # In a real implementation, this would generate the actual report
                self.logger.info(f"Generated quarterly benchmark report: {report_path}")
            
            else:
                self.logger.warning(f"Unknown report type: {report_type}")
                return None
            
            # Move report to scheduled reports directory
            if report_path and os.path.exists(report_path):
                scheduled_dir = self.config['report_settings']['storage_path']
                os.makedirs(scheduled_dir, exist_ok=True)
                
                new_filename = f"{schedule_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{os.path.splitext(report_path)[1]}"
                new_path = os.path.join(scheduled_dir, new_filename)
                
                shutil.move(report_path, new_path)
                report_path = new_path
            
            return report_path
            
        except Exception as e:
            self.logger.error(f"Error generating {report_type} report: {e}")
            return None
    
    def send_report_email(self, recipients: List[str], subject: str, 
                         report_path: str, report_type: str, schedule_name: str) -> bool:
        """Send report via email"""
        try:
            email_config = self.config['email_settings']
            
            # Create email message
            msg = MimeMultipart()
            msg['Subject'] = subject
            msg['From'] = email_config['from_address']
            msg['To'] = ', '.join(recipients)
            
            # Email body
            body = self.generate_email_body(report_type, schedule_name)
            msg.attach(MimeText(body, 'html'))
            
            # Attach report
            with open(report_path, 'rb') as file:
                attachment = MimeApplication(file.read(), Name=os.path.basename(report_path))
                attachment['Content-Disposition'] = f'attachment; filename="{os.path.basename(report_path)}"'
                msg.attach(attachment)
            
            # Send email
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                if email_config.get('username') and email_config.get('password'):
                    server.starttls()
                    server.login(email_config['username'], email_config['password'])
                
                server.send_message(msg)
            
            self.logger.info(f"Report email sent to {len(recipients)} recipients")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending report email: {e}")
            return False
    
    def generate_email_body(self, report_type: str, schedule_name: str) -> str:
        """Generate HTML email body"""
        current_date = datetime.now().strftime('%B %d, %Y')
        
        email_templates = {
            "performance": {
                "title": "Daily Performance Report",
                "description": "Overview of vendor performance metrics and key insights from the past 24 hours."
            },
            "comprehensive": {
                "title": "Weekly Vendor Summary",
                "description": "Comprehensive analysis of vendor relationships, performance trends, and strategic recommendations."
            },
            "analytics": {
                "title": "Monthly Analytics Report",
                "description": "Detailed analytics and insights into vendor performance, risk assessment, and improvement opportunities."
            },
            "quarterly": {
                "title": "Quarterly Vendor Review",
                "description": "Executive summary of vendor performance, benchmark comparisons, and strategic outlook for the next quarter."
            }
        }
        
        template = email_templates.get(report_type, {
            "title": "Vendor Report",
            "description": "Automated vendor management report."
        })
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }}
                .content {{ background: #f9f9f9; padding: 20px; border-radius: 5px; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{template['title']}</h1>
                    <p>{current_date}</p>
                </div>
                
                <div class="content">
                    <p>Dear Stakeholder,</p>
                    
                    <p>{template['description']}</p>
                    
                    <p>The attached report contains:</p>
                    <ul>
                        <li>Performance metrics and trends</li>
                        <li>Risk assessment and alerts</li>
                        <li>Strategic recommendations</li>
                        <li>Benchmark comparisons</li>
                    </ul>
                    
                    <p>This report was automatically generated by the Vendor Performance Management System.</p>
                    
                    <p>For questions or additional information, please contact the Vendor Management Office.</p>
                </div>
                
                <div class="footer">
                    <p>This is an automated email. Please do not reply to this message.</p>
                    <p>Vendor Performance Management System | {current_date}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_body
    
    def log_report_generation(self, schedule_name: str, report_type: str, report_path: Optional[str],
                            recipients: List[str], email_sent: bool, success: bool, 
                            error_message: str = None):
        """Log report generation activity"""
        try:
            cursor = self.conn.cursor()
            
            # Create report_logs table if not exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS report_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_name TEXT,
                report_type TEXT,
                report_path TEXT,
                generation_time TIMESTAMP,
                recipients TEXT,
                email_sent BOOLEAN,
                success BOOLEAN,
                error_message TEXT
            )
            ''')
            
            cursor.execute('''
            INSERT INTO report_logs 
            (schedule_name, report_type, report_path, generation_time, recipients, email_sent, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                schedule_name,
                report_type,
                report_path,
                datetime.now().isoformat(),
                json.dumps(recipients),
                email_sent,
                success,
                error_message
            ))
            
            self.conn.commit()
            
        except Exception as e:
            self.logger.error(f"Error logging report generation: {e}")
    
    def cleanup_old_reports(self):
        """Remove reports older than retention period"""
        try:
            retention_days = self.config['report_settings']['retention_days']
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            report_dir = self.config['report_settings']['storage_path']
            if not os.path.exists(report_dir):
                return
            
            reports_removed = 0
            for filename in os.listdir(report_dir):
                file_path = os.path.join(report_dir, filename)
                
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_time < cutoff_date:
                        try:
                            os.remove(file_path)
                            reports_removed += 1
                            self.logger.info(f"Removed old report: {filename}")
                        except Exception as e:
                            self.logger.warning(f"Failed to remove old report {filename}: {e}")
            
            if reports_removed > 0:
                self.logger.info(f"Cleaned up {reports_removed} old reports")
                
        except Exception as e:
            self.logger.error(f"Report cleanup failed: {e}")
    
    def get_report_history(self, days: int = 30) -> List[Dict]:
        """Get report generation history"""
        try:
            cursor = self.conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor.execute('''
            SELECT schedule_name, report_type, generation_time, success, email_sent, error_message
            FROM report_logs
            WHERE generation_time > ?
            ORDER BY generation_time DESC
            ''', (cutoff_date,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'schedule_name': row[0],
                    'report_type': row[1],
                    'generation_time': row[2],
                    'success': bool(row[3]),
                    'email_sent': bool(row[4]),
                    'error_message': row[5]
                })
            
            return history
            
        except Exception as e:
            self.logger.error(f"Error getting report history: {e}")
            return []
    
    def run_scheduler(self):
        """Run the scheduler continuously"""
        try:
            self.logger.info("Starting report scheduler...")
            
            while True:
                try:
                    # Run pending scheduled tasks
                    schedule.run_pending()
                    
                    # Run cleanup once per day
                    if datetime.now().hour == 2 and datetime.now().minute == 0:  # 2:00 AM
                        self.cleanup_old_reports()
                    
                    time.sleep(60)  # Check every minute
                    
                except KeyboardInterrupt:
                    self.logger.info("Scheduler stopped by user")
                    break
                except Exception as e:
                    self.logger.error(f"Scheduler error: {e}")
                    time.sleep(300)  # Wait 5 minutes before retrying
                    
        except Exception as e:
            self.logger.error(f"Scheduler failed: {e}")

def main():
    """Main function for script execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Vendor Dashboard Report Scheduler')
    parser.add_argument('--run', action='store_true', help='Run scheduler continuously')
    parser.add_argument('--generate', type=str, help='Generate specific report immediately')
    parser.add_argument('--history', type=int, help='Show report history for last N days')
    parser.add_argument('--cleanup', action='store_true', help='Cleanup old reports')
    
    args = parser.parse_args()
    
    scheduler = ReportScheduler()
    
    if args.generate:
        # Generate specific report immediately
        schedule_config = scheduler.config['schedules'].get(args.generate)
        if schedule_config:
            scheduler.generate_scheduled_report(args.generate, schedule_config)
        else:
            print(f"Unknown schedule: {args.generate}")
            sys.exit(1)
    
    elif args.history:
        # Show report history
        history = scheduler.get_report_history(args.history)
        print(json.dumps(history, indent=2))
    
    elif args.cleanup:
        # Cleanup old reports
        scheduler.cleanup_old_reports()
        print("Report cleanup completed")
    
    elif args.run:
        # Run scheduler continuously
        scheduler.run_scheduler()
    
    else:
        # Show current schedules
        print("Current Report Schedules:")
        for job in schedule.get_jobs():
            print(f"  {job.tags}: {job}")

if __name__ == "__main__":
    main()
