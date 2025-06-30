"""Guideline mapping configuration loader for cancer type routing."""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class GuidelineConfigLoader:
    """Loads and manages guideline mapping configuration from CSV file."""
    
    def __init__(self, config_path: str = "config/guideline_mapping.csv"):
        """Initialize the config loader.
        
        Args:
            config_path: Path to the CSV configuration file
        """
        self.config_path = Path(config_path)
        self.logger = logging.getLogger("guideline_config")
        self._mapping = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from CSV file."""
        try:
            if not self.config_path.exists():
                self.logger.error(f"Guideline mapping file not found: {self.config_path}")
                self._create_default_mapping()
                return
            
            with open(self.config_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    cancer_type = row['cancer_type'].strip()
                    body_part = row['body_part'].strip()
                    guideline_store = row['guideline_store'].strip()
                    status = row['status'].strip()
                    notes = row.get('notes', '').strip()
                    
                    # Use body_part as the key for mapping (matches existing system)
                    self._mapping[body_part.lower()] = {
                        'cancer_type': cancer_type,
                        'guideline_store': guideline_store,
                        'status': status,
                        'notes': notes
                    }
            
            self.logger.info(f"Loaded {len(self._mapping)} guideline mappings from {self.config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to load guideline config: {str(e)}")
            self._create_default_mapping()
    
    def _create_default_mapping(self):
        """Create default mapping as fallback."""
        self.logger.warning("Using default hardcoded mapping as fallback")
        self._mapping = {
            # Available guidelines
            "oral cavity": {"guideline_store": "oral_oropharyngeal", "status": "available"},
            "oropharynx": {"guideline_store": "oral_oropharyngeal", "status": "available"},
            "oropharyngeal": {"guideline_store": "oral_oropharyngeal", "status": "available"},
            "mouth": {"guideline_store": "oral_oropharyngeal", "status": "available"},
            "tongue": {"guideline_store": "oral_oropharyngeal", "status": "available"},
            
            # Unavailable guidelines
            "hypopharynx": {"guideline_store": "UNAVAILABLE", "status": "unavailable"},
            "lung": {"guideline_store": "UNAVAILABLE", "status": "unavailable"},
            "breast": {"guideline_store": "UNAVAILABLE", "status": "unavailable"},
        }
    
    def get_guideline_mapping(self) -> Dict[str, str]:
        """Get the mapping in the format expected by existing retrieve_guideline.py.
        
        Returns:
            Dictionary mapping body part to guideline store name
        """
        return {
            body_part: config['guideline_store'] 
            for body_part, config in self._mapping.items()
        }
    
    def get_guideline_info(self, body_part: str) -> Optional[Dict[str, str]]:
        """Get detailed guideline information for a body part.
        
        Args:
            body_part: Body part to look up
            
        Returns:
            Dictionary with guideline information or None if not found
        """
        return self._mapping.get(body_part.lower())
    
    def is_available(self, body_part: str) -> bool:
        """Check if guidelines are available for a body part.
        
        Args:
            body_part: Body part to check
            
        Returns:
            True if guidelines are available
        """
        info = self.get_guideline_info(body_part)
        return info is not None and info['status'] == 'available'
    
    def is_unavailable(self, body_part: str) -> bool:
        """Check if guidelines are explicitly unavailable for a body part.
        
        Args:
            body_part: Body part to check
            
        Returns:
            True if guidelines are explicitly unavailable
        """
        info = self.get_guideline_info(body_part)
        return info is not None and info['status'] == 'unavailable'
    
    def get_available_cancer_types(self) -> List[str]:
        """Get list of cancer types with available guidelines.
        
        Returns:
            List of cancer types with available guidelines
        """
        return [
            body_part for body_part, config in self._mapping.items()
            if config['status'] == 'available'
        ]
    
    def get_unavailable_cancer_types(self) -> List[str]:
        """Get list of cancer types without available guidelines.
        
        Returns:
            List of cancer types without available guidelines (empty for simplified approach)
        """
        # In simplified approach, we don't track unavailable types
        # All unmapped types automatically use general guidelines
        return []
    
    def add_new_guideline(self, cancer_type: str, body_part: str, guideline_store: str, notes: str = ""):
        """Add a new guideline mapping (updates both memory and CSV file).
        
        Args:
            cancer_type: Cancer type identifier
            body_part: Body part name
            guideline_store: Guideline store name
            notes: Optional notes
        """
        # Update in-memory mapping
        self._mapping[body_part.lower()] = {
            'cancer_type': cancer_type,
            'guideline_store': guideline_store,
            'status': 'available',
            'notes': notes
        }
        
        # Update CSV file
        self._save_config()
        self.logger.info(f"Added new guideline mapping: {body_part} -> {guideline_store}")
    
    def mark_as_unavailable(self, body_part: str, notes: str = ""):
        """Mark a cancer type as explicitly unavailable.
        
        Args:
            body_part: Body part name
            notes: Optional notes about unavailability
        """
        if body_part.lower() in self._mapping:
            self._mapping[body_part.lower()]['status'] = 'unavailable'
            self._mapping[body_part.lower()]['guideline_store'] = 'UNAVAILABLE'
            if notes:
                self._mapping[body_part.lower()]['notes'] = notes
        else:
            self._mapping[body_part.lower()] = {
                'cancer_type': body_part,
                'guideline_store': 'UNAVAILABLE',
                'status': 'unavailable',
                'notes': notes
            }
        
        self._save_config()
        self.logger.info(f"Marked as unavailable: {body_part}")
    
    def _save_config(self):
        """Save current mapping back to CSV file."""
        try:
            with open(self.config_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['cancer_type', 'body_part', 'guideline_store', 'status', 'notes']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for body_part, config in sorted(self._mapping.items()):
                    writer.writerow({
                        'cancer_type': config.get('cancer_type', body_part),
                        'body_part': body_part,
                        'guideline_store': config['guideline_store'],
                        'status': config['status'],
                        'notes': config.get('notes', '')
                    })
            
            self.logger.info(f"Saved guideline mapping to {self.config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save guideline config: {str(e)}")
    
    def reload_config(self):
        """Reload configuration from CSV file."""
        self._mapping = {}
        self._load_config()
        self.logger.info("Reloaded guideline configuration")

# Global instance for easy access
guideline_config = GuidelineConfigLoader()