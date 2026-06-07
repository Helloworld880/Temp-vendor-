#!/usr/bin/env python3
"""
Automated Backup Script for Vendor Dashboard
Performs database backups, file backups, and system state snapshots
"""

import os
import sys
import sqlite3
import json
import shutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import zipfile
import hashlib
import pandas as pd

class BackupManager:
    def __init__(self, config_path: str = "config/backup_config.json"):
        self.config = self.load_config(config_path)
        self.setup_logging()
        self.backup_path = self.config.get('backup_path', 'data/backups/')
        
    def load_config(self, config_path: str) -> Dict:
        """Load backup configuration"""
        default_config = {
            "backup_path": "data/backups/",
            "retention_days": 30,
            "backup_schedule": "daily",
            "include_database": True,
            "include_files": True,
            "include_reports": True,
            "compression": True,
            "encryption": False,
            "max_backup_size_gb": 10,
            "notify_on_completion": True,
            "notify_on_failure": True
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
        except Exception as e:
            logging.warning(f"Could not load backup config: {e}")
            
        return default_config
    
    def setup_logging(self):
        """Setup logging for backup operations"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/backup.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def perform_backup(self) -> bool:
        """Perform complete system backup"""
        try:
            self.logger.info("Starting automated backup process")
            
            # Create backup directory
            backup_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join(self.backup_path, f"backup_{backup_timestamp}")
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_results = {
                'timestamp': backup_timestamp,
                'backup_dir': backup_dir,
                'components': {},
                'success': True
            }
            
            # Backup database
            if self.config.get('include_database', True):
                db_result = self.backup_database(backup_dir)
                backup_results['components']['database'] = db_result
                if not db_result['success']:
                    backup_results['success'] = False
            
            # Backup data files
            if self.config.get('include_files', True):
                files_result = self.backup_data_files(backup_dir)
                backup_results['components']['files'] = files_result
                if not files_result['success']:
                    backup_results['success'] = False
            
            # Backup reports
            if self.config.get('include_reports', True):
                reports_result = self.backup_reports(backup_dir)
                backup_results['components']['reports'] = reports_result
                if not reports_result['success']:
                    backup_results['success'] = False
            
            # Create backup manifest
            self.create_backup_manifest(backup_dir, backup_results)
            
            # Compress backup
            if self.config.get('compression', True):
                compress_result = self.compress_backup(backup_dir)
                backup_results['compression'] = compress_result
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            # Log backup completion
            if backup_results['success']:
                self.logger.info(f"Backup completed successfully: {backup_dir}")
                if self.config.get('notify_on_completion', True):
                    self.send_notification("Backup Completed", f"Backup {backup_timestamp} completed successfully")
            else:
                self.logger.error(f"Backup completed with errors: {backup_dir}")
                if self.config.get('notify_on_failure', True):
                    self.send_notification("Backup Failed", f"Backup {backup_timestamp} completed with errors")
            
            return backup_results['success']
            
        except Exception as e:
            self.logger.error(f"Backup process failed: {e}")
            if self.config.get('notify_on_failure', True):
                self.send_notification("Backup Process Failed", str(e))
            return False
    
    def backup_database(self, backup_dir: str) -> Dict:
        """Backup SQLite database"""
        try:
            db_path = "data/vendors.db"
            if not os.path.exists(db_path):
                return {'success': False, 'error': 'Database file not found'}
            
            # Create database backup
            backup_db_path = os.path.join(backup_dir, "vendors.db")
            
            # Use SQLite backup API for proper backup
            source_conn = sqlite3.connect(db_path)
            backup_conn = sqlite3.connect(backup_db_path)
            
            source_conn.backup(backup_conn)
            
            source_conn.close()
            backup_conn.close()
            
            # Export critical tables to CSV for redundancy
            csv_dir = os.path.join(backup_dir, "csv_exports")
            os.makedirs(csv_dir, exist_ok=True)
            
            self.export_tables_to_csv(db_path, csv_dir)
            
            file_size = os.path.getsize(backup_db_path)
            
            self.logger.info(f"Database backup completed: {backup_db_path} ({file_size} bytes)")
            
            return {
                'success': True,
                'file_path': backup_db_path,
                'file_size': file_size,
                'tables_exported': ['vendors', 'performance_metrics', 'financial_metrics', 'risk_assessments']
            }
            
        except Exception as e:
            self.logger.error(f"Database backup failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def export_tables_to_csv(self, db_path: str, export_dir: str):
        """Export database tables to CSV files"""
        try:
            conn = sqlite3.connect(db_path)
            
            tables = [
                'vendors', 'performance_metrics', 'financial_metrics', 
                'risk_assessments', 'users', 'audit_logs'
            ]
            
            for table in tables:
                try:
                    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                    csv_path = os.path.join(export_dir, f"{table}.csv")
                    df.to_csv(csv_path, index=False)
                    self.logger.info(f"Exported {table} to CSV: {len(df)} records")
                except Exception as e:
                    self.logger.warning(f"Failed to export table {table}: {e}")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"CSV export failed: {e}")
    
    def backup_data_files(self, backup_dir: str) -> Dict:
        """Backup data files and configurations"""
        try:
            data_dir = "data/"
            config_dir = "config/"
            
            backup_data = {
                'success': True,
                'files_backed_up': [],
                'total_size': 0
            }
            
            # Backup data files (excluding database)
            data_files = []
            for root, dirs, files in os.walk(data_dir):
                for file in files:
                    if not file.endswith('.db'):  # Exclude database files
                        file_path = os.path.join(root, file)
                        data_files.append(file_path)
            
            # Backup configuration files
            if os.path.exists(config_dir):
                for root, dirs, files in os.walk(config_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        data_files.append(file_path)
            
            # Copy files to backup directory
            for file_path in data_files:
                try:
                    relative_path = os.path.relpath(file_path)
                    backup_file_path = os.path.join(backup_dir, relative_path)
                    
                    # Create directory structure
                    os.makedirs(os.path.dirname(backup_file_path), exist_ok=True)
                    
                    shutil.copy2(file_path, backup_file_path)
                    
                    file_size = os.path.getsize(backup_file_path)
                    backup_data['files_backed_up'].append({
                        'file': relative_path,
                        'size': file_size
                    })
                    backup_data['total_size'] += file_size
                    
                except Exception as e:
                    self.logger.warning(f"Failed to backup file {file_path}: {e}")
            
            self.logger.info(f"Data files backup completed: {len(backup_data['files_backed_up'])} files")
            
            return backup_data
            
        except Exception as e:
            self.logger.error(f"Data files backup failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def backup_reports(self, backup_dir: str) -> Dict:
        """Backup generated reports"""
        try:
            reports_dir = "reports/"
            if not os.path.exists(reports_dir):
                return {'success': True, 'message': 'No reports directory found'}
            
            reports_backup_dir = os.path.join(backup_dir, "reports")
            os.makedirs(reports_backup_dir, exist_ok=True)
            
            report_files = []
            for root, dirs, files in os.walk(reports_dir):
                for file in files:
                    if file.endswith(('.pdf', '.xlsx', '.html', '.csv')):
                        file_path = os.path.join(root, file)
                        report_files.append(file_path)
            
            # Backup recent reports (last 7 days)
            recent_reports = []
            cutoff_date = datetime.now() - timedelta(days=7)
            
            for report_file in report_files:
                file_time = datetime.fromtimestamp(os.path.getmtime(report_file))
                if file_time >= cutoff_date:
                    recent_reports.append(report_file)
            
            # Copy recent reports
            backed_up_reports = []
            total_size = 0
            
            for report_file in recent_reports:
                try:
                    backup_file = os.path.join(reports_backup_dir, os.path.basename(report_file))
                    shutil.copy2(report_file, backup_file)
                    
                    file_size = os.path.getsize(backup_file)
                    backed_up_reports.append({
                        'file': os.path.basename(report_file),
                        'size': file_size,
                        'modified': datetime.fromtimestamp(os.path.getmtime(report_file)).isoformat()
                    })
                    total_size += file_size
                    
                except Exception as e:
                    self.logger.warning(f"Failed to backup report {report_file}: {e}")
            
            self.logger.info(f"Reports backup completed: {len(backed_up_reports)} reports")
            
            return {
                'success': True,
                'reports_backed_up': backed_up_reports,
                'total_size': total_size
            }
            
        except Exception as e:
            self.logger.error(f"Reports backup failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def create_backup_manifest(self, backup_dir: str, backup_results: Dict):
        """Create backup manifest file"""
        try:
            manifest_path = os.path.join(backup_dir, "backup_manifest.json")
            
            manifest = {
                'backup_id': backup_results['timestamp'],
                'created_at': datetime.now().isoformat(),
                'system_version': '2.0.0',
                'components': backup_results['components'],
                'total_size': self.calculate_backup_size(backup_dir),
                'checksum': self.calculate_checksum(backup_dir)
            }
            
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            self.logger.info(f"Backup manifest created: {manifest_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to create backup manifest: {e}")
    
    def calculate_backup_size(self, backup_dir: str) -> int:
        """Calculate total size of backup directory"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(backup_dir):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                total_size += os.path.getsize(filepath)
        return total_size
    
    def calculate_checksum(self, backup_dir: str) -> str:
        """Calculate checksum for backup verification"""
        try:
            hasher = hashlib.sha256()
            
            # Get all files and sort for consistent hashing
            all_files = []
            for root, dirs, files in os.walk(backup_dir):
                for file in files:
                    if file != "backup_manifest.json":  # Exclude manifest from checksum
                        filepath = os.path.join(root, file)
                        all_files.append(filepath)
            
            all_files.sort()
            
            for filepath in all_files:
                with open(filepath, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hasher.update(chunk)
            
            return hasher.hexdigest()
            
        except Exception as e:
            self.logger.error(f"Failed to calculate checksum: {e}")
            return ""
    
    def compress_backup(self, backup_dir: str) -> Dict:
        """Compress backup directory"""
        try:
            zip_path = f"{backup_dir}.zip"
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(backup_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, backup_dir)
                        zipf.write(file_path, arcname)
            
            # Calculate compression ratio
            original_size = self.calculate_backup_size(backup_dir)
            compressed_size = os.path.getsize(zip_path)
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            # Remove original backup directory
            shutil.rmtree(backup_dir)
            
            self.logger.info(f"Backup compressed: {zip_path} ({compression_ratio:.1f}% reduction)")
            
            return {
                'success': True,
                'compressed_path': zip_path,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': compression_ratio
            }
            
        except Exception as e:
            self.logger.error(f"Backup compression failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def cleanup_old_backups(self):
        """Remove backups older than retention period"""
        try:
            retention_days = self.config.get('retention_days', 30)
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            if not os.path.exists(self.backup_path):
                return
            
            backups_removed = 0
            for item in os.listdir(self.backup_path):
                item_path = os.path.join(self.backup_path, item)
                
                # Get modification time
                if os.path.isdir(item_path):
                    mod_time = datetime.fromtimestamp(os.path.getmtime(item_path))
                elif item.endswith('.zip'):
                    mod_time = datetime.fromtimestamp(os.path.getmtime(item_path))
                else:
                    continue
                
                if mod_time < cutoff_date:
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                        backups_removed += 1
                        self.logger.info(f"Removed old backup: {item}")
                    except Exception as e:
                        self.logger.warning(f"Failed to remove old backup {item}: {e}")
            
            if backups_removed > 0:
                self.logger.info(f"Cleaned up {backups_removed} old backups")
                
        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {e}")
    
    def send_notification(self, subject: str, message: str):
        """Send backup notification"""
        try:
            # In a real implementation, this would send email/slack notifications
            self.logger.info(f"NOTIFICATION - {subject}: {message}")
            
            # Example: Save notification to file for monitoring systems
            notification = {
                'timestamp': datetime.now().isoformat(),
                'subject': subject,
                'message': message,
                'type': 'backup'
            }
            
            notifications_file = 'logs/backup_notifications.json'
            os.makedirs(os.path.dirname(notifications_file), exist_ok=True)
            
            # Append to notifications file
            with open(notifications_file, 'a') as f:
                f.write(json.dumps(notification) + '\n')
                
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
    
    def verify_backup(self, backup_path: str) -> bool:
        """Verify backup integrity"""
        try:
            if not os.path.exists(backup_path):
                self.logger.error(f"Backup path does not exist: {backup_path}")
                return False
            
            # Check if it's a compressed backup
            if backup_path.endswith('.zip'):
                return self.verify_compressed_backup(backup_path)
            else:
                return self.verify_directory_backup(backup_path)
                
        except Exception as e:
            self.logger.error(f"Backup verification failed: {e}")
            return False
    
    def verify_compressed_backup(self, zip_path: str) -> bool:
        """Verify compressed backup integrity"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                # Test zip file integrity
                bad_file = zipf.testzip()
                if bad_file is not None:
                    self.logger.error(f"Corrupted file in backup: {bad_file}")
                    return False
                
                # Check for manifest
                if 'backup_manifest.json' not in zipf.namelist():
                    self.logger.error("Backup manifest missing")
                    return False
            
            self.logger.info(f"Compressed backup verified: {zip_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Compressed backup verification failed: {e}")
            return False
    
    def verify_directory_backup(self, backup_dir: str) -> bool:
        """Verify directory backup integrity"""
        try:
            manifest_path = os.path.join(backup_dir, "backup_manifest.json")
            
            if not os.path.exists(manifest_path):
                self.logger.error("Backup manifest missing")
                return False
            
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            # Verify checksum
            expected_checksum = manifest.get('checksum', '')
            if expected_checksum:
                actual_checksum = self.calculate_checksum(backup_dir)
                if expected_checksum != actual_checksum:
                    self.logger.error("Backup checksum mismatch")
                    return False
            
            # Verify critical files exist
            critical_files = [
                "vendors.db",
                "backup_manifest.json"
            ]
            
            for critical_file in critical_files:
                if not os.path.exists(os.path.join(backup_dir, critical_file)):
                    self.logger.error(f"Critical file missing: {critical_file}")
                    return False
            
            self.logger.info(f"Directory backup verified: {backup_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"Directory backup verification failed: {e}")
            return False

def main():
    """Main function for script execution"""
    backup_manager = BackupManager()
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Vendor Dashboard Backup Utility')
    parser.add_argument('--verify', type=str, help='Verify specific backup')
    parser.add_argument('--list', action='store_true', help='List available backups')
    parser.add_argument('--force', action='store_true', help='Force backup execution')
    
    args = parser.parse_args()
    
    if args.verify:
        success = backup_manager.verify_backup(args.verify)
        sys.exit(0 if success else 1)
    
    elif args.list:
        backup_manager.list_backups()
    
    else:
        success = backup_manager.perform_backup()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()