"""Test structured JSON outputs for Ollama and OpenAI."""

import asyncio
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from config.llm_providers_structured import (
    create_structured_provider,
    TStagingResponse,
    NStagingResponse,
    DetectionResponse
)


async def test_ollama_structured():
    """Test Ollama structured output."""
    print("\n=== Testing Ollama Structured Output ===")
    
    try:
        provider = create_structured_provider("ollama", {
            "model": "qwen2.5:7b",
            "base_url": "http://localhost:11434"
        })
        
        # Test T staging
        prompt = """
        Analyze this report for T staging:
        
        AJCC Guidelines: T1: Tumor ≤2cm, T2: Tumor >2cm but ≤4cm, T3: Tumor >4cm, T4: Tumor invades adjacent structures
        
        Report: MRI shows a 3.5cm mass in the right tongue base with extension to the soft palate.
        No invasion of deep muscle structures noted.
        """
        
        result = await provider.generate_structured(prompt, TStagingResponse)
        print(f"\nT Staging Result:")
        print(f"- Stage: {result['t_stage']}")
        print(f"- Confidence: {result['confidence']}")
        print(f"- Rationale: {result['rationale']}")
        print(f"- Tumor size: {result['extracted_info'].get('tumor_size')}")
        
        # Test detection
        detect_prompt = """
        Identify the body part and cancer type from this report:
        Clinical information: Oral cavity, base of tongue, left, biopsy shows squamous cell carcinoma.
        """
        
        detect_result = await provider.generate_structured(detect_prompt, DetectionResponse)
        print(f"\nDetection Result:")
        print(f"- Body part: {detect_result['body_part']}")
        print(f"- Cancer type: {detect_result['cancer_type']}")
        print(f"- Confidence: {detect_result['confidence']}")
        
    except Exception as e:
        print(f"Ollama test failed: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_openai_structured():
    """Test OpenAI structured output."""
    print("\n=== Testing OpenAI Structured Output ===")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Skipping OpenAI test - no API key found")
        return
    
    try:
        provider = create_structured_provider("openai", {
            "api_key": api_key,
            "model": "gpt-3.5-turbo"
        })
        
        # Test N staging
        prompt = """
        Analyze this report for N staging:
        
        AJCC Guidelines: N0: No nodes, N1: Single ipsilateral node ≤3cm, N2: Multiple nodes or >3cm, N3: Nodes >6cm
        
        Report: Multiple enlarged lymph nodes in right neck level II, largest measuring 2.5cm with central necrosis.
        Additional nodes at level III measuring 1.2cm. No contralateral nodes.
        """
        
        result = await provider.generate_structured(prompt, NStagingResponse)
        print(f"\nN Staging Result:")
        print(f"- Stage: {result['n_stage']}")
        print(f"- Confidence: {result['confidence']}")
        print(f"- Rationale: {result['rationale']}")
        print(f"- Node info: {result['node_info']}")
        
    except Exception as e:
        print(f"OpenAI test failed: {str(e)}")


async def test_fallback_parsing():
    """Test fallback parsing when structured output not available."""
    print("\n=== Testing Fallback JSON Parsing ===")
    
    # Simulate a response that needs parsing
    test_response = """
    Based on the analysis:
    {
        "t_stage": "T2",
        "confidence": 0.85,
        "rationale": "Tumor measures 3.5cm which is >2cm but ≤4cm, meeting T2 criteria",
        "extracted_info": {
            "tumor_size": "3.5cm",
            "largest_dimension": 3.5,
            "invasions": [],
            "extensions": ["soft palate"],
            "multiple_tumors": false,
            "key_findings": ["3.5cm mass", "extension to soft palate"]
        }
    }
    """
    
    import json
    import re
    
    # Extract JSON
    json_match = re.search(r'\{.*\}', test_response, re.DOTALL)
    if json_match:
        data = json.loads(json_match.group(0))
        validated = TStagingResponse(**data)
        print(f"Successfully parsed and validated:")
        print(f"- Stage: {validated.t_stage}")
        print(f"- Confidence: {validated.confidence}")
    else:
        print("Failed to extract JSON")


async def main():
    """Run all tests."""
    print("Testing Structured JSON Outputs for TN Staging System")
    print("=" * 50)
    
    # Check Ollama availability
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            await test_ollama_structured()
        else:
            print("Ollama not available - skipping Ollama tests")
    except:
        print("Ollama not running - skipping Ollama tests")
    
    # Test OpenAI if available
    await test_openai_structured()
    
    # Test fallback parsing
    await test_fallback_parsing()
    
    print("\n" + "=" * 50)
    print("Testing complete!")
    
    print("\n📝 Implementation Summary:")
    print("1. Created structured providers with Pydantic models")
    print("2. OpenAI: Uses response_format={'type': 'json_object'}")
    print("3. Ollama: Uses format parameter with JSON schema")
    print("4. Fallback: Standard generation + regex parsing")
    print("5. Benefits: Type safety, validation, fewer parsing errors")


if __name__ == "__main__":
    asyncio.run(main())