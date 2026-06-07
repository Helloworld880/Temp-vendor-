#!/usr/bin/env python3
"""
Data Synchronization Script for Vendor Dashboard
Synchronizes data with external systems (ERP, CRM, etc.)
"""

import os
import sys
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class DataSyncManager:
    def __init__(self, config_path: str = "config/sync_config.json"):
        self.config = self.load_config(config_path)
        self.setup_logging()
        self.setup_database()
        
    def load_config(self, config_path: str) -> Dict:
        """Load synchronization configuration"""
        default_config = {
            "sync_schedule": "hourly",
            "systems": {
                "erp": {
                    "enabled": False,
                    "type": "sap",
                    "endpoint": "",
                    "auth_type": "basic",
                    "sync_vendors": True,
                    "sync_financials": True
                },
                "crm": {
                    "enabled": False,
                    "type": "salesforce",
                    "endpoint": "",
                    "auth_type": "oauth2",
                    "sync_contacts": True,
                    "sync_activities": True
                },
                "external_apis": {
                    "dun_bradstreet": {
                        "enabled": False,
                        "api_key": "",
                        "sync_company_data": True
                    }
                }
            },
            "batch_size": 100,
            "max_retries": 3,
            "retry_delay": 5
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
        except Exception as e:
            logging.warning(f"Could not load sync config: {e}")
            
        return default_config
    
    def setup_logging(self):
        """Setup logging for synchronization operations"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/data_sync.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_database(self):
        """Setup database connection"""
        self.db_path = "data/vendors.db"
        self.conn = sqlite3.connect(self.db_path)
    
    def perform_full_sync(self) -> Dict:
        """Perform full data synchronization"""
        try:
            self.logger.info("Starting full data synchronization")
            
            sync_results = {
                'timestamp': datetime.now().isoformat(),
                'systems': {},
                'success': True
            }
            
            # Sync with ERP system
            if self.config['systems']['erp']['enabled']:
                erp_result = self.sync_with_erp()
                sync_results['systems']['erp'] = erp_result
                if not erp_result['success']:
                    sync_results['success'] = False
            
            # Sync with CRM system
            if self.config['systems']['crm']['enabled']:
                crm_result = self.sync_with_crm()
                sync_results['systems']['crm'] = crm_result
                if not crm_result['success']:
                    sync_results['success'] = False
            
            # Sync with external APIs
            if self.config['systems']['external_apis']['dun_bradstreet']['enabled']:
                dnb_result = self.sync_with_dun_bradstreet()
                sync_results['systems']['dun_bradstreet'] = dnb_result
                if not dnb_result['success']:
                    sync_results['success'] = False
            
            # Update sync history
            self.update_sync_history(sync_results)
            
            if sync_results['success']:
                self.logger.info("Full data synchronization completed successfully")
            else:
                self.logger.warning("Data synchronization completed with errors")
            
            return sync_results
            
        except Exception as e:
            self.logger.error(f"Full data synchronization failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def sync_with_erp(self) -> Dict:
        """Synchronize data with ERP system"""
        try:
            erp_config = self.config['systems']['erp']
            erp_type = erp_config['type']
            
            self.logger.info(f"Starting ERP synchronization ({erp_type})")
            
            sync_results = {
                'system': 'erp',
                'type': erp_type,
                'timestamp': datetime.now().isoformat(),
                'operations': [],
                'success': True
            }
            
            # Sync vendors
            if erp_config.get('sync_vendors', True):
                vendor_result = self.sync_vendors_with_erp()
                sync_results['operations'].append(vendor_result)
                if not vendor_result['success']:
                    sync_results['success'] = False
            
            # Sync financial data
            if erp_config.get('sync_financials', True):
                financial_result = self.sync_financials_with_erp()
                sync_results['operations'].append(financial_result)
                if not financial_result['success']:
                    sync_results['success'] = False
            
            self.logger.info(f"ERP synchronization completed: {len(sync_results['operations'])} operations")
            
            return sync_results
            
        except Exception as e:
            self.logger.error(f"ERP synchronization failed: {e}")
            return {'success': False, 'error': str(e), 'system': 'erp'}
    
    def sync_vendors_with_erp(self) -> Dict:
        """Synchronize vendor data with ERP"""
        try:
            # Get vendors that need synchronization
            vendors_to_sync = self.get_vendors_for_sync('erp')
            
            if not vendors_to_sync:
                return {'operation': 'vendor_sync', 'success': True, 'message': 'No vendors to sync'}
            
            # In a real implementation, this would call ERP APIs
            # For now, we'll simulate the sync process
            
            synced_count = 0
            errors = []
            
            for vendor in vendors_to_sync:
                try:
                    # Simulate API call to ERP system
                    sync_success = self.simulate_erp_vendor_sync(vendor)
                    
                    if sync_success:
                        self.mark_vendor_synced(vendor['vendor_id'], 'erp')
                        synced_count += 1
                    else:
                        errors.append(f"Failed to sync vendor {vendor['vendor_name']}")
                        
                except Exception as e:
                    errors.append(f"Error syncing vendor {vendor['vendor_name']}: {str(e)}")
            
            result = {
                'operation': 'vendor_sync',
                'success': len(errors) == 0,
                'vendors_processed': len(vendors_to_sync),
                'vendors_synced': synced_count,
                'errors': errors
            }
            
            self.logger.info(f"Vendor sync completed: {synced_count}/{len(vendors_to_sync)} vendors synced")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Vendor sync with ERP failed: {e}")
            return {'operation': 'vendor_sync', 'success': False, 'error': str(e)}
    
    def sync_financials_with_erp(self) -> Dict:
        """Synchronize financial data with ERP"""
        try:
            # Get financial data that needs synchronization
            financial_data_to_sync = self.get_financial_data_for_sync()
            
            if not financial_data_to_sync:
                return {'operation': 'financial_sync', 'success': True, 'message': 'No financial data to sync'}
            
            synced_count = 0
            errors = []
            
            for financial_record in financial_data_to_sync:
                try:
                    # Simulate API call to ERP system
                    sync_success = self.simulate_erp_financial_sync(financial_record)
                    
                    if sync_success:
                        self.mark_financial_synced(financial_record['financial_id'], 'erp')
                        synced_count += 1
                    else:
                        errors.append(f"Failed to sync financial record {financial_record['financial_id']}")
                        
                except Exception as e:
                    errors.append(f"Error syncing financial record {financial_record['financial_id']}: {str(e)}")
            
            result = {
                'operation': 'financial_sync',
                'success': len(errors) == 0,
                'records_processed': len(financial_data_to_sync),
                'records_synced': synced_count,
                'errors': errors
            }
            
            self.logger.info(f"Financial sync completed: {synced_count}/{len(financial_data_to_sync)} records synced")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Financial sync with ERP failed: {e}")
            return {'operation': 'financial_sync', 'success': False, 'error': str(e)}
    
    def sync_with_crm(self) -> Dict:
        """Synchronize data with CRM system"""
        try:
            crm_config = self.config['systems']['crm']
            crm_type = crm_config['type']
            
            self.logger.info(f"Starting CRM synchronization ({crm_type})")
            
            sync_results = {
                'system': 'crm',
                'type': crm_type,
                'timestamp': datetime.now().isoformat(),
                'operations': [],
                'success': True
            }
            
            # Sync vendor contacts
            if crm_config.get('sync_contacts', True):
                contacts_result = self.sync_contacts_with_crm()
                sync_results['operations'].append(contacts_result)
                if not contacts_result['success']:
                    sync_results['success'] = False
            
            # Sync activities
            if crm_config.get('sync_activities', True):
                activities_result = self.sync_activities_with_crm()
                sync_results['operations'].append(activities_result)
                if not activities_result['success']:
                    sync_results['success'] = False
            
            self.logger.info(f"CRM synchronization completed: {len(sync_results['operations'])} operations")
            
            return sync_results
            
        except Exception as e:
            self.logger.error(f"CRM synchronization failed: {e}")
            return {'success': False, 'error': str(e), 'system': 'crm'}
    
    def sync_contacts_with_crm(self) -> Dict:
        """Synchronize vendor contacts with CRM"""
        try:
            # Get contacts that need synchronization
            contacts_to_sync = self.get_contacts_for_sync()
            
            if not contacts_to_sync:
                return {'operation': 'contact_sync', 'success': True, 'message': 'No contacts to sync'}
            
            synced_count = 0
            errors = []
            
            for contact in contacts_to_sync:
                try:
                    # Simulate CRM API call
                    sync_success = self.simulate_crm_contact_sync(contact)
                    
                    if sync_success:
                        self.mark_contact_synced(contact['contact_id'], 'crm')
                        synced_count += 1
                    else:
                        errors.append(f"Failed to sync contact {contact['contact_name']}")
                        
                except Exception as e:
                    errors.append(f"Error syncing contact {contact['contact_name']}: {str(e)}")
            
            result = {
                'operation': 'contact_sync',
                'success': len(errors) == 0,
                'contacts_processed': len(contacts_to_sync),
                'contacts_synced': synced_count,
                'errors': errors
            }
            
            self.logger.info(f"Contact sync completed: {synced_count}/{len(contacts_to_sync)} contacts synced")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Contact sync with CRM failed: {e}")
            return {'operation': 'contact_sync', 'success': False, 'error': str(e)}
    
    def sync_with_dun_bradstreet(self) -> Dict:
        """Synchronize data with Dun & Bradstreet API"""
        try:
            dnb_config = self.config['systems']['external_apis']['dun_bradstreet']
            
            self.logger.info("Starting Dun & Bradstreet synchronization")
            
            sync_results = {
                'system': 'dun_bradstreet',
                'timestamp': datetime.now().isoformat(),
                'operations': [],
                'success': True
            }
            
            # Sync company data
            if dnb_config.get('sync_company_data', True):
                company_result = self.sync_company_data_with_dnb()
                sync_results['operations'].append(company_result)
                if not company_result['success']:
                    sync_results['success'] = False
            
            self.logger.info("Dun & Bradstreet synchronization completed")
            
            return sync_results
            
        except Exception as e:
            self.logger.error(f"Dun & Bradstreet synchronization failed: {e}")
            return {'success': False, 'error': str(e), 'system': 'dun_bradstreet'}
    
    def sync_company_data_with_dnb(self) -> Dict:
        """Synchronize company data with Dun & Bradstreet"""
        try:
            # Get vendors that need D&B data
            vendors_for_dnb = self.get_vendors_for_dnb_sync()
            
            if not vendors_for_dnb:
                return {'operation': 'company_data_sync', 'success': True, 'message': 'No vendors need D&B data'}
            
            updated_count = 0
            errors = []
            
            for vendor in vendors_for_dnb:
                try:
                    # Simulate D&B API call
                    dnb_data = self.simulate_dnb_api_call(vendor)
                    
                    if dnb_data:
                        self.update_vendor_with_dnb_data(vendor['vendor_id'], dnb_data)
                        updated_count += 1
                    else:
                        errors.append(f"Failed to get D&B data for {vendor['vendor_name']}")
                        
                except Exception as e:
                    errors.append(f"Error getting D&B data for {vendor['vendor_name']}: {str(e)}")
            
            result = {
                'operation': 'company_data_sync',
                'success': len(errors) == 0,
                'vendors_processed': len(vendors_for_dnb),
                'vendors_updated': updated_count,
                'errors': errors
            }
            
            self.logger.info(f"D&B sync completed: {updated_count}/{len(vendors_for_dnb)} vendors updated")
            
            return result
            
        except Exception as e:
            self.logger.error(f"D&B company data sync failed: {e}")
            return {'operation': 'company_data_sync', 'success': False, 'error': str(e)}
    
    # Helper methods for data retrieval
    def get_vendors_for_sync(self, system: str) -> List[Dict]:
        """Get vendors that need synchronization with specified system"""
        try:
            cursor = self.conn.cursor()
            
            # Get vendors modified since last sync or never synced
            query = """
            SELECT v.*, MAX(s.last_sync_time) as last_sync
            FROM vendors v
            LEFT JOIN sync_history s ON v.vendor_id = s.record_id AND s.system = ? AND s.record_type = 'vendor'
            WHERE v.last_modified > COALESCE(s.last_sync_time, '1900-01-01')
            OR s.last_sync_time IS NULL
            GROUP BY v.vendor_id
            LIMIT ?
            """
            
            cursor.execute(query, (system, self.config.get('batch_size', 100)))
            vendors = cursor.fetchall()
            
            # Convert to list of dictionaries
            vendor_list = []
            for vendor in vendors:
                vendor_dict = {
                    'vendor_id': vendor[0],
                    'vendor_name': vendor[1],
                    'category': vendor[2],
                    'contact_email': vendor[3],
                    'contact_phone': vendor[4],
                    'address': vendor[5],
                    'contract_value': vendor[6],
                    'contract_start_date': vendor[7],
                    'contract_end_date': vendor[8],
                    'status': vendor[9],
                    'risk_level': vendor[10]
                }
                vendor_list.append(vendor_dict)
            
            return vendor_list
            
        except Exception as e:
            self.logger.error(f"Error getting vendors for sync: {e}")
            return []
    
    def get_financial_data_for_sync(self) -> List[Dict]:
        """Get financial data that needs synchronization"""
        try:
            cursor = self.conn.cursor()
            
            query = """
            SELECT f.*, v.vendor_name
            FROM financial_metrics f
            JOIN vendors v ON f.vendor_id = v.vendor_id
            WHERE f.last_modified > COALESCE(
                (SELECT MAX(last_sync_time) FROM sync_history 
                 WHERE record_id = f.financial_id AND system = 'erp' AND record_type = 'financial'),
                '1900-01-01'
            )
            LIMIT ?
            """
            
            cursor.execute(query, (self.config.get('batch_size', 100),))
            financial_data = cursor.fetchall()
            
            financial_list = []
            for record in financial_data:
                financial_dict = {
                    'financial_id': record[0],
                    'vendor_id': record[1],
                    'vendor_name': record[9],
                    'period': record[2],
                    'revenue': record[3],
                    'cost_savings': record[4],
                    'roi': record[5],
                    'profit_margin': record[6],
                    'payment_terms': record[7],
                    'payment_status': record[8]
                }
                financial_list.append(financial_dict)
            
            return financial_list
            
        except Exception as e:
            self.logger.error(f"Error getting financial data for sync: {e}")
            return []
    
    def get_contacts_for_sync(self) -> List[Dict]:
        """Get contacts that need synchronization with CRM"""
        try:
            # This would typically query a contacts table
            # For now, we'll extract from vendors table
            cursor = self.conn.cursor()
            
            query = """
            SELECT vendor_id, vendor_name, contact_email, contact_phone
            FROM vendors
            WHERE contact_email IS NOT NULL AND contact_email != ''
            LIMIT ?
            """
            
            cursor.execute(query, (self.config.get('batch_size', 100),))
            contacts = cursor.fetchall()
            
            contact_list = []
            for contact in contacts:
                contact_dict = {
                    'contact_id': f"vendor_{contact[0]}",
                    'contact_name': contact[1],
                    'email': contact[2],
                    'phone': contact[3],
                    'company': contact[1],
                    'type': 'vendor_contact'
                }
                contact_list.append(contact_dict)
            
            return contact_list
            
        except Exception as e:
            self.logger.error(f"Error getting contacts for sync: {e}")
            return []
    
    def get_vendors_for_dnb_sync(self) -> List[Dict]:
        """Get vendors that need Dun & Bradstreet data"""
        try:
            cursor = self.conn.cursor()
            
            query = """
            SELECT v.*
            FROM vendors v
            LEFT JOIN vendor_dnb_data d ON v.vendor_id = d.vendor_id
            WHERE d.vendor_id IS NULL OR d.last_updated < date('now', '-30 days')
            LIMIT ?
            """
            
            cursor.execute(query, (self.config.get('batch_size', 100),))
            vendors = cursor.fetchall()
            
            vendor_list = []
            for vendor in vendors:
                vendor_dict = {
                    'vendor_id': vendor[0],
                    'vendor_name': vendor[1],
                    'address': vendor[5]
                }
                vendor_list.append(vendor_dict)
            
            return vendor_list
            
        except Exception as e:
            self.logger.error(f"Error getting vendors for D&B sync: {e}")
            return []
    
    # Simulation methods (would be real API calls in production)
    def simulate_erp_vendor_sync(self, vendor: Dict) -> bool:
        """Simulate ERP vendor synchronization"""
        # In production, this would make actual API calls
        # For simulation, we'll just log and return success
        self.logger.info(f"Simulating ERP sync for vendor: {vendor['vendor_name']}")
        return True
    
    def simulate_erp_financial_sync(self, financial_record: Dict) -> bool:
        """Simulate ERP financial data synchronization"""
        self.logger.info(f"Simulating ERP financial sync for: {financial_record['vendor_name']} - {financial_record['period']}")
        return True
    
    def simulate_crm_contact_sync(self, contact: Dict) -> bool:
        """Simulate CRM contact synchronization"""
        self.logger.info(f"Simulating CRM sync for contact: {contact['contact_name']}")
        return True
    
    def simulate_dnb_api_call(self, vendor: Dict) -> Optional[Dict]:
        """Simulate Dun & Bradstreet API call"""
        self.logger.info(f"Simulating D&B API call for: {vendor['vendor_name']}")
        
        # Simulate D&B response data
        dnb_data = {
            'duns_number': f"0{vendor['vendor_id']:08d}",
            'company_name': vendor['vendor_name'],
            'address': vendor.get('address', ''),
            'business_risk_score': 85 - (vendor['vendor_id'] % 40),  # Simulated score
            'financial_stress_score': 90 - (vendor['vendor_id'] % 50),  # Simulated score
            'corporate_linkage': 'Independent',
            'industry_code': '45-49' if vendor['vendor_id'] % 2 == 0 else '50-51',
            'employee_count': (vendor['vendor_id'] % 100) * 50,
            'annual_revenue': vendor.get('contract_value', 0) * 12,
            'data_confidence': 'High',
            'last_updated': datetime.now().isoformat()
        }
        
        return dnb_data
    
    # Database update methods
    def mark_vendor_synced(self, vendor_id: int, system: str):
        """Mark vendor as synced with specified system"""
        try:
            cursor = self.conn.cursor()
            
            cursor.execute('''
            INSERT OR REPLACE INTO sync_history 
            (record_id, record_type, system, last_sync_time, sync_status)
            VALUES (?, ?, ?, ?, ?)
            ''', (vendor_id, 'vendor', system, datetime.now().isoformat(), 'success'))
            
            self.conn.commit()
            
        except Exception as e:
            self.logger.error(f"Error marking vendor as synced: {e}")
    
    def mark_financial_synced(self, financial_id: int, system: str):
        """Mark financial record as synced"""
        try:
            cursor = self.conn.cursor()
            
            cursor.execute('''
            INSERT OR REPLACE INTO sync_history 
            (record_id, record_type, system, last_sync_time, sync_status)
            VALUES (?, ?, ?, ?, ?)
            ''', (financial_id, 'financial', system, datetime.now().isoformat(), 'success'))
            
            self.conn.commit()
            
        except Exception as e:
            self.logger.error(f"Error marking financial record as synced: {e}")
    
    def mark_contact_synced(self, contact_id: str, system: str):
        """Mark contact as synced"""
        try:
            cursor = self.conn.cursor()
            
            cursor.execute('''
            INSERT OR REPLACE INTO sync_history 
            (record_id, record_type, system, last_sync_time, sync_status)
            VALUES (?, ?, ?, ?, ?)
            ''', (contact_id, 'contact', system, datetime.now().isoformat(), 'success'))
            
            self.conn.commit()
            
        except Exception as e:
            self.logger.error(f"Error marking contact as synced: {e}")
    
    def update_vendor_with_dnb_data(self, vendor_id: int, dnb_data: Dict):
        """Update vendor with D&B data"""
        try:
            cursor = self.conn.cursor()
            
            # Create or update vendor_dnb_data table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS vendor_dnb_data (
                vendor_id INTEGER PRIMARY KEY,
                duns_number TEXT,
                business_risk_score REAL,
                financial_stress_score REAL,
                corporate_linkage TEXT,
                industry_code TEXT,
                employee_count INTEGER,
                annual_revenue REAL,
                data_confidence TEXT,
                last_updated TIMESTAMP,
                FOREIGN KEY (vendor_id) REFERENCES vendors (vendor_id)
            )
            ''')
            
            # Insert or update D&B data
            cursor.execute('''
            INSERT OR REPLACE INTO vendor_dnb_data 
            (vendor_id, duns_number, business_risk_score, financial_stress_score, 
             corporate_linkage, industry_code, employee_count, annual_revenue, 
             data_confidence, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                vendor_id,
                dnb_data['duns_number'],
                dnb_data['business_risk_score'],
                dnb_data['financial_stress_score'],
                dnb_data['corporate_linkage'],
                dnb_data['industry_code'],
                dnb_data['employee_count'],
                dnb_data['annual_revenue'],
                dnb_data['data_confidence'],
                dnb_data['last_updated']
            ))
            
            self.conn.commit()
            
            self.logger.info(f"Updated vendor {vendor_id} with D&B data")
            
        except Exception as e:
            self.logger.error(f"Error updating vendor with D&B data: {e}")
    
    def update_sync_history(self, sync_results: Dict):
        """Update synchronization history"""
        try:
            cursor = self.conn.cursor()
            
            # Create sync_history table if not exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER,
                record_type TEXT,
                system TEXT,
                last_sync_time TIMESTAMP,
                sync_status TEXT,
                error_message TEXT
            )
            ''')
            
            # Create sync_summary table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_timestamp TIMESTAMP,
                system TEXT,
                operation TEXT,
                records_processed INTEGER,
                records_synced INTEGER,
                success_rate REAL,
                duration_seconds REAL,
                status TEXT
            )
            ''')
            
            # Insert sync summary
            for system, system_results in sync_results.get('systems', {}).items():
                for operation in system_results.get('operations', []):
                    cursor.execute('''
                    INSERT INTO sync_summary 
                    (sync_timestamp, system, operation, records_processed, records_synced, success_rate, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        sync_results['timestamp'],
                        system,
                        operation['operation'],
                        operation.get('records_processed', 0),
                        operation.get('records_synced', 0),
                        operation.get('records_synced', 0) / max(operation.get('records_processed', 1), 1),
                        'success' if operation.get('success', False) else 'failed'
                    ))
            
            self.conn.commit()
            
        except Exception as e:
            self.logger.error(f"Error updating sync history: {e}")
    
    def get_sync_status(self) -> Dict:
        """Get current synchronization status"""
        try:
            cursor = self.conn.cursor()
            
            # Get last sync times for each system
            cursor.execute('''
            SELECT system, MAX(last_sync_time) as last_sync, 
                   COUNT(*) as total_records,
                   SUM(CASE WHEN sync_status = 'success' THEN 1 ELSE 0 END) as successful_records
            FROM sync_history
            GROUP BY system
            ''')
            
            sync_status = {}
            for row in cursor.fetchall():
                system, last_sync, total_records, successful_records = row
                sync_status[system] = {
                    'last_sync': last_sync,
                    'total_records': total_records,
                    'successful_records': successful_records,
                    'success_rate': successful_records / max(total_records, 1)
                }
            
            return sync_status
            
        except Exception as e:
            self.logger.error(f"Error getting sync status: {e}")
            return {}

def main():
    """Main function for script execution"""
    sync_manager = DataSyncManager()
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Vendor Dashboard Data Sync Utility')
    parser.add_argument('--system', type=str, help='Sync specific system (erp|crm|dnb|all)')
    parser.add_argument('--status', action='store_true', help='Show sync status')
    parser.add_argument('--force', action='store_true', help='Force full sync')
    
    args = parser.parse_args()
    
    if args.status:
        status = sync_manager.get_sync_status()
        print(json.dumps(status, indent=2))
        sys.exit(0)
    
    elif args.system:
        if args.system.lower() == 'erp':
            result = sync_manager.sync_with_erp()
        elif args.system.lower() == 'crm':
            result = sync_manager.sync_with_crm()
        elif args.system.lower() == 'dnb':
            result = sync_manager.sync_with_dun_bradstreet()
        elif args.system.lower() == 'all':
            result = sync_manager.perform_full_sync()
        else:
            print(f"Unknown system: {args.system}")
            sys.exit(1)
        
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get('success', False) else 1)
    
    else:
        # Default: perform full sync
        result = sync_manager.perform_full_sync()
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get('success', False) else 1)

if __name__ == "__main__":
    main()