#!/usr/bin/env python3
"""
Utility script for managing guideline mappings.
Usage: python config/manage_guidelines.py [command] [options]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.guideline_config import guideline_config

def list_guidelines():
    """List all current guideline mappings."""
    print("📋 Current Guideline Mappings:")
    print("=" * 50)
    
    mapping = guideline_config.get_guideline_mapping()
    
    # Group by status
    available = []
    unavailable = []
    
    for body_part in sorted(mapping.keys()):
        info = guideline_config.get_guideline_info(body_part)
        if info and info['status'] == 'available':
            available.append((body_part, info))
        else:
            unavailable.append((body_part, info))
    
    print(f"\n✅ Available Guidelines ({len(available)}):")
    for body_part, info in available:
        store = info['guideline_store']
        notes = info.get('notes', '')
        print(f"  • {body_part:<20} → {store:<25} {notes}")
    
    print(f"\n❌ Unavailable Guidelines ({len(unavailable)}):")
    for body_part, info in unavailable:
        notes = info.get('notes', '')
        print(f"  • {body_part:<20} → UNAVAILABLE          {notes}")

def add_guideline(cancer_type: str, body_part: str, guideline_store: str, notes: str = ""):
    """Add a new guideline mapping."""
    try:
        guideline_config.add_new_guideline(cancer_type, body_part, guideline_store, notes)
        print(f"✅ Added: {body_part} → {guideline_store}")
        print(f"📝 Notes: {notes}")
    except Exception as e:
        print(f"❌ Error adding guideline: {str(e)}")

def mark_unavailable(body_part: str, notes: str = ""):
    """Mark a cancer type as unavailable."""
    try:
        guideline_config.mark_as_unavailable(body_part, notes)
        print(f"❌ Marked as unavailable: {body_part}")
        print(f"📝 Notes: {notes}")
    except Exception as e:
        print(f"❌ Error marking unavailable: {str(e)}")

def check_status(body_part: str):
    """Check the status of a specific body part."""
    info = guideline_config.get_guideline_info(body_part)
    
    if info:
        status = info['status']
        store = info['guideline_store']
        notes = info.get('notes', '')
        
        if status == 'available':
            print(f"✅ {body_part}: Available → {store}")
        else:
            print(f"❌ {body_part}: Unavailable")
        
        if notes:
            print(f"📝 Notes: {notes}")
    else:
        print(f"❓ {body_part}: Not found in configuration")

def reload_config():
    """Reload configuration from CSV file."""
    try:
        guideline_config.reload_config()
        print("✅ Configuration reloaded from CSV file")
    except Exception as e:
        print(f"❌ Error reloading configuration: {str(e)}")

def validate_config():
    """Validate the current configuration."""
    print("🔍 Validating Configuration:")
    print("=" * 50)
    
    try:
        available = guideline_config.get_available_cancer_types()
        unavailable = guideline_config.get_unavailable_cancer_types()
        
        print(f"✅ Configuration loaded successfully")
        print(f"📊 Available: {len(available)} cancer types")
        print(f"❌ Unavailable: {len(unavailable)} cancer types")
        print(f"📄 Total: {len(available) + len(unavailable)} entries")
        
        # Check for common issues
        if not available:
            print("⚠️  Warning: No available guidelines configured")
        
        # Check for duplicate entries in different states
        all_parts = set(available + unavailable)
        if len(all_parts) != len(available) + len(unavailable):
            print("⚠️  Warning: Potential duplicate entries detected")
        
        print("\n🎯 Ready for use in TN staging system")
        
    except Exception as e:
        print(f"❌ Configuration validation failed: {str(e)}")

def main():
    parser = argparse.ArgumentParser(
        description="Manage guideline mappings for TN staging system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python config/manage_guidelines.py list                          # List all mappings
  python config/manage_guidelines.py add lung lung lung_guidelines # Add new guideline
  python config/manage_guidelines.py unavailable thyroid           # Mark as unavailable
  python config/manage_guidelines.py check "oral cavity"           # Check specific status
  python config/manage_guidelines.py reload                        # Reload from CSV
  python config/manage_guidelines.py validate                      # Validate config
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # List command
    subparsers.add_parser('list', help='List all guideline mappings')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add new guideline mapping')
    add_parser.add_argument('cancer_type', help='Cancer type identifier')
    add_parser.add_argument('body_part', help='Body part name')
    add_parser.add_argument('guideline_store', help='Guideline store name')
    add_parser.add_argument('--notes', default='', help='Optional notes')
    
    # Unavailable command
    unavail_parser = subparsers.add_parser('unavailable', help='Mark cancer type as unavailable')
    unavail_parser.add_argument('body_part', help='Body part name')
    unavail_parser.add_argument('--notes', default='No specific AJCC guidelines available', help='Notes about unavailability')
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check status of specific body part')
    check_parser.add_argument('body_part', help='Body part name to check')
    
    # Reload command
    subparsers.add_parser('reload', help='Reload configuration from CSV file')
    
    # Validate command
    subparsers.add_parser('validate', help='Validate current configuration')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'list':
        list_guidelines()
    elif args.command == 'add':
        add_guideline(args.cancer_type, args.body_part, args.guideline_store, args.notes)
    elif args.command == 'unavailable':
        mark_unavailable(args.body_part, args.notes)
    elif args.command == 'check':
        check_status(args.body_part)
    elif args.command == 'reload':
        reload_config()
    elif args.command == 'validate':
        validate_config()

if __name__ == "__main__":
    main()