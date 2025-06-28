#!/usr/bin/env python3
"""Check if structured JSON outputs are actually being used in production logs."""

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any

def check_recent_logs():
    """Check recent log files for structured output indicators."""
    print("=== Checking Recent Log Files for Structured Output Usage ===\n")
    
    # Find recent log files
    log_dir = Path("logs")
    if not log_dir.exists():
        print("❌ No logs directory found")
        return
    
    log_files = sorted(log_dir.glob("session_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not log_files:
        print("❌ No session log files found")
        return
    
    # Check the most recent log file
    recent_log = log_files[0]
    print(f"📋 Analyzing most recent log: {recent_log.name}")
    
    try:
        with open(recent_log, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # Look for structured output indicators
        indicators = {
            "StructuredOllamaProvider": log_content.count("StructuredOllamaProvider"),
            "generate_structured": log_content.count("generate_structured"),
            "TStagingResponse": log_content.count("TStagingResponse"),
            "NStagingResponse": log_content.count("NStagingResponse"),
            "Pydantic": log_content.count("Pydantic"),
            "structured output": log_content.count("structured output"),
            "JSON schema": log_content.count("JSON schema"),
            "manual parsing": log_content.count("manual parsing"),
            "fallback to manual": log_content.count("fallback to manual"),
        }
        
        print("🔍 Structured Output Indicators:")
        for indicator, count in indicators.items():
            status = "✅" if count > 0 else "❌"
            print(f"   {status} {indicator}: {count} occurrences")
        
        # Look for T and N staging calls
        t_staging_calls = re.findall(r'T staging.*(?:generate|response)', log_content, re.IGNORECASE)
        n_staging_calls = re.findall(r'N staging.*(?:generate|response)', log_content, re.IGNORECASE)
        
        print(f"\n📊 Staging Calls Found:")
        print(f"   T staging related: {len(t_staging_calls)} calls")
        print(f"   N staging related: {len(n_staging_calls)} calls")
        
        # Look for JSON parsing errors or successes
        json_errors = log_content.count("JSONDecodeError") + log_content.count("JSON parsing failed")
        json_success = log_content.count("JSON parsed successfully") + log_content.count("structured generation")
        
        print(f"\n🔧 JSON Processing:")
        print(f"   JSON errors: {json_errors}")
        print(f"   JSON success indicators: {json_success}")
        
        # Check for provider type mentions
        if "StructuredOllamaProvider" in log_content:
            print("\n✅ GOOD: StructuredOllamaProvider is being used!")
        elif "OllamaProvider" in log_content:
            print("\n⚠️ WARNING: Regular OllamaProvider detected, structured provider may not be active")
        
        return indicators, log_content
        
    except Exception as e:
        print(f"❌ Error reading log file: {str(e)}")
        return None, None

def check_recent_jsonl():
    """Check recent JSONL files for structured output patterns."""
    print("\n=== Checking Recent JSONL Files ===\n")
    
    # Find recent JSONL files in logs directory
    log_dir = Path("logs")
    if not log_dir.exists():
        print("❌ No logs directory found")
        return None, None, None
    
    jsonl_files = sorted(log_dir.glob("session_*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not jsonl_files:
        print("❌ No JSONL session files found")
        return None, None, None
    
    recent_jsonl = jsonl_files[0]
    print(f"📋 Analyzing most recent JSONL: {recent_jsonl.name}")
    
    try:
        structured_calls = 0
        manual_calls = 0
        staging_responses = []
        
        with open(recent_jsonl, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    data = json.loads(line.strip())
                    
                    # Check for T/N staging responses
                    if 'context_T' in data or 'context_N' in data:
                        staging_responses.append(data)
                    
                    # Check for structured vs manual indicators
                    content_str = json.dumps(data).lower()
                    if 'structured' in content_str:
                        structured_calls += 1
                    if 'manual' in content_str or 'fallback' in content_str:
                        manual_calls += 1
                        
                except json.JSONDecodeError:
                    continue
        
        print(f"📊 JSONL Analysis:")
        print(f"   Structured indicators: {structured_calls}")
        print(f"   Manual/fallback indicators: {manual_calls}")
        print(f"   Staging responses found: {len(staging_responses)}")
        
        # Analyze staging responses for format quality
        if staging_responses:
            latest_staging = staging_responses[-1]
            print(f"\n🔍 Latest Staging Response Format:")
            
            # Check T staging format
            if 'context_T' in latest_staging:
                print(f"   T stage: {latest_staging.get('context_T', 'N/A')}")
                print(f"   T confidence: {latest_staging.get('context_CT', 'N/A')}")
            
            # Check N staging format  
            if 'context_N' in latest_staging:
                print(f"   N stage: {latest_staging.get('context_N', 'N/A')}")
                print(f"   N confidence: {latest_staging.get('context_CN', 'N/A')}")
                
            # Check for extracted info quality
            if 'metadata' in latest_staging:
                metadata = latest_staging['metadata']
                if 'tumor_info' in metadata:
                    tumor_info = metadata['tumor_info']
                    largest_dim = tumor_info.get('largest_dimension', 'N/A')
                    print(f"   Largest dimension: {largest_dim}")
                    
                    # Check if units are included
                    if isinstance(largest_dim, str) and ('cm' in largest_dim or 'mm' in largest_dim):
                        print("   ✅ Units properly included in dimension")
                    elif isinstance(largest_dim, (int, float)):
                        print("   ⚠️ Dimension is numeric without units (old format)")
                    else:
                        print(f"   ❓ Dimension format unclear: {type(largest_dim)}")
        
        return structured_calls, manual_calls, staging_responses
        
    except Exception as e:
        print(f"❌ Error reading JSONL file: {str(e)}")
        return None, None, None

def check_provider_configuration():
    """Check if the main system is configured to use structured providers."""
    print("\n=== Checking Provider Configuration ===\n")
    
    try:
        # Check main.py for structured provider imports and usage
        with open("main.py", 'r') as f:
            main_content = f.read()
        
        checks = {
            "Structured import": "llm_providers_structured" in main_content,
            "create_structured_provider": "create_structured_provider" in main_content,
            "StructuredOllamaProvider": "StructuredOllamaProvider" in main_content,
            "LLMProviderFactory": "LLMProviderFactory" in main_content,
        }
        
        print("🔧 Main.py Configuration:")
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check}: {'Found' if result else 'Not found'}")
        
        # Check if agents have structured methods
        agents_to_check = ["agents/staging_t.py", "agents/staging_n.py"]
        
        for agent_file in agents_to_check:
            if os.path.exists(agent_file):
                with open(agent_file, 'r') as f:
                    agent_content = f.read()
                
                has_structured = "_determine_t_stage_structured" in agent_content or "_determine_n_stage_structured" in agent_content
                has_manual = "_determine_t_stage_manual" in agent_content or "_determine_n_stage_manual" in agent_content
                
                print(f"\n📁 {agent_file}:")
                print(f"   ✅ Structured method: {'Found' if has_structured else 'Not found'}")
                print(f"   ✅ Manual fallback: {'Found' if has_manual else 'Not found'}")
        
        return checks
        
    except Exception as e:
        print(f"❌ Error checking configuration: {str(e)}")
        return None

def main():
    """Run all structured output checks."""
    print("🔍 STRUCTURED JSON OUTPUT USAGE VERIFICATION\n")
    print("=" * 60)
    
    # Check logs
    log_indicators, log_content = check_recent_logs()
    
    # Check JSONL
    structured_calls, manual_calls, staging_responses = check_recent_jsonl()
    
    # Check configuration
    config_checks = check_provider_configuration()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    
    if log_indicators and any(count > 0 for count in [log_indicators.get("StructuredOllamaProvider", 0), 
                                                     log_indicators.get("generate_structured", 0)]):
        print("✅ Structured outputs appear to be ACTIVE in logs")
    else:
        print("❌ No structured output indicators found in logs")
    
    if staging_responses:
        latest = staging_responses[-1]
        if 'metadata' in latest and 'tumor_info' in latest['metadata']:
            largest_dim = latest['metadata']['tumor_info'].get('largest_dimension', '')
            if isinstance(largest_dim, str) and ('cm' in largest_dim or 'mm' in largest_dim):
                print("✅ Unit formatting is CORRECT (includes cm/mm)")
            else:
                print("⚠️ Unit formatting may not be using structured outputs")
    
    if config_checks and config_checks.get("create_structured_provider", False):
        print("✅ Configuration is SET UP for structured outputs")
    else:
        print("❌ Configuration may not be using structured providers")
    
    print("\n🎯 RECOMMENDATION:")
    if log_indicators and log_indicators.get("StructuredOllamaProvider", 0) > 0:
        print("   System appears to be using structured outputs correctly!")
    else:
        print("   System may still be using manual JSON parsing - investigate further")

if __name__ == "__main__":
    main()