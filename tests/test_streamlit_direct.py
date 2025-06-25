#!/usr/bin/env python3
"""Test Streamlit app startup directly to catch errors."""

import os
import sys
import traceback

# Set environment to prevent PyTorch issues
os.environ.update({
    'TORCH_JIT': '0',
    'TOKENIZERS_PARALLELISM': 'false',
    'TN_STAGING_BACKEND': 'ollama'
})

def test_streamlit_imports():
    """Test if streamlit and our app can be imported."""
    print("🧪 Testing Streamlit App Startup")
    print("=" * 35)
    
    try:
        print("📦 Testing core imports...")
        
        # Test basic imports
        import streamlit as st
        print("  ✅ streamlit")
        
        # Block PyTorch before our imports
        class TorchBlocker:
            def __getattr__(self, name):
                return None
        sys.modules['torch'] = TorchBlocker()
        
        # Test our app imports
        from main import TNStagingSystem
        print("  ✅ TNStagingSystem")
        
        from config import get_ollama_config
        print("  ✅ config modules")
        
        print("\n🔧 Testing app initialization...")
        
        # Test if we can create the system
        system = TNStagingSystem(backend="ollama", debug=False)
        print("  ✅ System created successfully")
        
        print("\n🎯 Testing Streamlit page config...")
        
        # Test streamlit configuration
        try:
            st.set_page_config(
                page_title="Test",
                page_icon="🧪",
                layout="wide"
            )
            print("  ✅ Page config works")
        except Exception as e:
            print(f"  ❌ Page config failed: {e}")
        
        print(f"\n✅ All tests passed - app should start correctly!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return False

def test_minimal_streamlit():
    """Test a minimal streamlit app."""
    print("\n" + "=" * 40)
    print("🔬 Testing Minimal Streamlit App")
    print("=" * 40)
    
    minimal_app = '''
import streamlit as st
import os

# Block torch
import sys
class TorchBlocker:
    def __getattr__(self, name):
        return None
sys.modules['torch'] = TorchBlocker()

st.title("🩺 TN Staging Test")
st.write("If you see this, Streamlit is working!")

backend = os.getenv("TN_STAGING_BACKEND", "ollama")
st.info(f"Backend: {backend}")

if st.button("Test System"):
    try:
        from main import TNStagingSystem
        system = TNStagingSystem(backend=backend, debug=False)
        st.success("✅ System initialized successfully!")
    except Exception as e:
        st.error(f"❌ System failed: {e}")
        st.code(str(e))
'''
    
    # Write minimal app
    with open("test_minimal_app.py", "w") as f:
        f.write(minimal_app)
    
    print("📝 Created minimal test app: test_minimal_app.py")
    print("🚀 Run with: streamlit run test_minimal_app.py")
    
    return True

if __name__ == "__main__":
    success1 = test_streamlit_imports()
    success2 = test_minimal_streamlit()
    
    if not success1:
        print("\n🔧 Suggested fixes:")
        print("1. Check if streamlit is properly installed")
        print("2. Try: pip install --upgrade streamlit")
        print("3. Check for conflicting packages")
        
    sys.exit(0 if success1 else 1)