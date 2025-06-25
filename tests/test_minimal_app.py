
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
