# Sandbox Implementation Guide for TN Staging System

## Overview

This document provides comprehensive guidance for implementing secure sandbox environments for the TN Staging System to handle sensitive medical data safely while maintaining development flexibility.

## Sandbox Approaches Comparison

### 1. Containerized Sandbox (Docker/Podman)

**Purpose**: Complete application isolation with ephemeral data handling

#### Pros ✅
- **Complete Isolation**: Full environment separation from host system
- **Ephemeral by Design**: Data destroyed when container stops
- **Reproducible**: Consistent environment across development/testing
- **Easy Cleanup**: Simple `docker rm` removes all traces
- **Version Control**: Container configurations can be versioned
- **Multi-Environment**: Same container works on any Docker-compatible system

#### Cons ❌
- **Performance Overhead**: Container virtualization adds latency
- **Resource Usage**: Additional memory/CPU consumption
- **Complexity**: Requires Docker knowledge and container orchestration
- **Network Configuration**: May require port mapping and network setup
- **Volume Management**: Care needed to avoid accidental data persistence

#### Implementation Steps

**Step 1: Create Dockerfile**
```dockerfile
# TN Staging Secure Container
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1001 tnstaging
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
RUN chown -R tnstaging:tnstaging /app

# Switch to non-root user
USER tnstaging

# Configure ephemeral session storage
ENV SESSION_STORAGE_TYPE=memory
ENV LOG_LEVEL=INFO

# Expose port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8501/health')"

# Start application
CMD ["streamlit", "run", "tn_staging_gui.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

**Step 2: Create docker-compose.yml**
```yaml
version: '3.8'

services:
  tn-staging:
    build: .
    ports:
      - "8501:8501"
    environment:
      - SESSION_STORAGE_TYPE=memory
      - CLEANUP_ON_EXIT=true
      - MAX_SESSION_TIME=3600  # 1 hour
    volumes:
      # NO persistent volumes for security
      - /tmp  # Ephemeral temp storage only
    restart: "no"  # Don't restart to ensure cleanup
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,size=100m
    cap_drop:
      - ALL
    cap_add:
      - SETGID
      - SETUID
```

**Step 3: Run Container**
```bash
# Build container
docker build -t tn-staging-secure .

# Run with security options
docker run --rm \
  --security-opt no-new-privileges \
  --read-only \
  --tmpfs /tmp:noexec,nosuid,size=100m \
  -p 8501:8501 \
  tn-staging-secure

# Or use docker-compose
docker-compose up --build
```

### 2. In-Memory Encrypted Sandbox

**Purpose**: Fast, secure, production-ready data handling with encryption

#### Pros ✅
- **High Performance**: No I/O overhead, pure memory operations
- **Automatic Cleanup**: Garbage collection handles data destruction
- **Encryption at Rest**: Data encrypted even in memory
- **Fine-Grained Control**: Precise timeout and cleanup policies
- **HIPAA Compliance Ready**: Meets medical data security standards
- **Scalable**: Works well with load balancing and clustering

#### Cons ❌
- **Memory Limitations**: Limited by available RAM
- **No Persistence**: Data lost on application restart
- **Implementation Complexity**: Requires careful memory management
- **Debugging Difficulty**: Harder to inspect encrypted in-memory data
- **Key Management**: Requires secure encryption key handling

#### Implementation Steps

**Step 1: Create Encrypted Session Manager**
```python
# utils/secure_session_manager.py
import os
import time
import threading
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from contextlib import contextmanager
import weakref
import json

class SecureSessionManager:
    def __init__(self, default_timeout: int = 3600):
        self.default_timeout = default_timeout
        self._sessions: Dict[str, Dict] = {}
        self._session_locks: Dict[str, threading.RLock] = {}
        self._cleanup_thread = None
        self._key = self._generate_session_key()
        self._cipher = Fernet(self._key)
        self._start_cleanup_thread()
    
    def _generate_session_key(self) -> bytes:
        """Generate or retrieve encryption key"""
        key = os.environ.get('TN_SESSION_KEY')
        if not key:
            key = Fernet.generate_key()
            # In production, store this securely
            os.environ['TN_SESSION_KEY'] = key.decode()
        return key.encode() if isinstance(key, str) else key
    
    def create_session(self, session_id: str, timeout: Optional[int] = None) -> None:
        """Create new encrypted session"""
        timeout = timeout or self.default_timeout
        expiry = time.time() + timeout
        
        with self._get_session_lock(session_id):
            self._sessions[session_id] = {
                'data': {},
                'expiry': expiry,
                'created': time.time()
            }
    
    def store_data(self, session_id: str, key: str, data: Any) -> None:
        """Store encrypted data in session"""
        if session_id not in self._sessions:
            self.create_session(session_id)
        
        with self._get_session_lock(session_id):
            if self._is_expired(session_id):
                self._cleanup_session(session_id)
                raise ValueError(f"Session {session_id} has expired")
            
            # Encrypt sensitive data
            serialized_data = json.dumps(data, default=str)
            encrypted_data = self._cipher.encrypt(serialized_data.encode())
            self._sessions[session_id]['data'][key] = encrypted_data
    
    def retrieve_data(self, session_id: str, key: str) -> Any:
        """Retrieve and decrypt session data"""
        with self._get_session_lock(session_id):
            if session_id not in self._sessions or self._is_expired(session_id):
                return None
            
            encrypted_data = self._sessions[session_id]['data'].get(key)
            if encrypted_data is None:
                return None
            
            # Decrypt data
            decrypted_data = self._cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
    
    @contextmanager
    def session_context(self, session_id: str):
        """Context manager for safe session handling"""
        try:
            if session_id not in self._sessions:
                self.create_session(session_id)
            yield self
        finally:
            # Auto-cleanup on context exit
            self.cleanup_session(session_id)
    
    def cleanup_session(self, session_id: str) -> None:
        """Securely cleanup session data"""
        with self._get_session_lock(session_id):
            if session_id in self._sessions:
                # Overwrite memory before deletion
                session_data = self._sessions[session_id]
                for key in session_data['data']:
                    session_data['data'][key] = b'\x00' * 1024
                del self._sessions[session_id]
                del self._session_locks[session_id]
```

**Step 2: Integration with TN Staging System**
```python
# contexts/secure_context_manager.py
from utils.secure_session_manager import SecureSessionManager

class SecureContextManager:
    def __init__(self):
        self.session_manager = SecureSessionManager(timeout=3600)
    
    def store_analysis_context(self, session_id: str, context_data: Dict) -> None:
        """Store analysis context securely"""
        # Remove or redact sensitive information
        safe_context = self._sanitize_context(context_data)
        self.session_manager.store_data(session_id, 'analysis_context', safe_context)
    
    def get_analysis_context(self, session_id: str) -> Optional[Dict]:
        """Retrieve analysis context"""
        return self.session_manager.retrieve_data(session_id, 'analysis_context')
    
    def _sanitize_context(self, context: Dict) -> Dict:
        """Remove or redact sensitive medical information"""
        safe_context = context.copy()
        
        # Redact sensitive fields
        sensitive_fields = ['patient_name', 'mrn', 'dob', 'ssn']
        for field in sensitive_fields:
            if field in safe_context:
                safe_context[field] = '[REDACTED]'
        
        # Truncate long medical reports
        if 'context_R' in safe_context and len(safe_context['context_R']) > 1000:
            safe_context['context_R'] = safe_context['context_R'][:1000] + '[TRUNCATED]'
        
        return safe_context
```

### 3. Secure Enclave/Trusted Execution Environment

**Purpose**: Hardware-level security for HIPAA-compliant production deployments

#### Pros ✅
- **Hardware Security**: CPU-level isolation and encryption
- **Compliance Ready**: Meets strictest medical data requirements
- **Attestation**: Cryptographic proof of secure execution
- **Memory Protection**: Hardware-enforced memory encryption
- **Side-Channel Resistance**: Protection against advanced attacks

#### Cons ❌
- **Hardware Dependency**: Requires specific CPU features (Intel SGX, ARM TrustZone)
- **Complexity**: Significant implementation and operational complexity
- **Performance Impact**: Encryption/decryption overhead
- **Limited Availability**: Not available on all cloud platforms
- **Development Difficulty**: Specialized knowledge required

#### Implementation Steps

**Step 1: Check Hardware Support**
```bash
# Check for Intel SGX support
cpuid | grep SGX

# Check for ARM TrustZone
cat /proc/cpuinfo | grep -i trust
```

**Step 2: Use Cloud Secure Enclaves** (Recommended)
```python
# AWS Nitro Enclaves integration example
import boto3
from enclave_sdk import EnclaveClient

class SecureEnclaveSession:
    def __init__(self):
        self.enclave_client = EnclaveClient()
        self.enclave_id = None
    
    def create_secure_session(self, medical_data: str) -> str:
        """Process medical data in secure enclave"""
        
        # Create enclave instance
        response = self.enclave_client.run_enclave(
            enclave_image_path="tn-staging-enclave:latest",
            cpu_count=2,
            memory_mib=512
        )
        self.enclave_id = response['enclave_id']
        
        # Send data to enclave for processing
        result = self.enclave_client.send_message(
            enclave_id=self.enclave_id,
            message={
                'action': 'analyze_report',
                'data': medical_data
            }
        )
        
        return result['staging_result']
    
    def cleanup(self):
        """Terminate enclave and cleanup"""
        if self.enclave_id:
            self.enclave_client.terminate_enclave(self.enclave_id)
```

### 4. Temporary Encrypted Storage Sandbox

**Purpose**: Balanced approach with time-limited encrypted file storage

#### Pros ✅
- **Development Friendly**: Maintains debugging capabilities
- **Automatic Cleanup**: Time-based file expiration
- **Encryption at Rest**: Files encrypted on disk
- **Audit Trail**: Can maintain compliance logs
- **Crash Recovery**: Data survives application restarts

#### Cons ❌
- **Disk I/O Overhead**: File system operations add latency
- **Key Management**: Encryption key storage and rotation
- **Cleanup Reliability**: Depends on cleanup process execution
- **Storage Usage**: Accumulates disk space over time
- **Attack Surface**: Files on disk create additional attack vectors

#### Implementation Steps

**Step 1: Create Encrypted Temporary Storage**
```python
# utils/encrypted_temp_storage.py
import os
import time
import tempfile
import threading
from pathlib import Path
from cryptography.fernet import Fernet
import json
import schedule

class EncryptedTempStorage:
    def __init__(self, base_dir: str = None, default_ttl: int = 3600):
        self.base_dir = Path(base_dir or tempfile.gettempdir()) / "tn_staging_secure"
        self.base_dir.mkdir(exist_ok=True, mode=0o700)  # Restricted permissions
        self.default_ttl = default_ttl
        self.key = self._get_encryption_key()
        self.cipher = Fernet(self.key)
        self._start_cleanup_scheduler()
    
    def store_session(self, session_id: str, data: Dict, ttl: int = None) -> Path:
        """Store encrypted session data with expiration"""
        ttl = ttl or self.default_ttl
        expiry = time.time() + ttl
        
        session_data = {
            'data': data,
            'created': time.time(),
            'expiry': expiry
        }
        
        # Encrypt and store
        serialized = json.dumps(session_data, default=str)
        encrypted = self.cipher.encrypt(serialized.encode())
        
        file_path = self.base_dir / f"{session_id}.encrypted"
        with open(file_path, 'wb') as f:
            f.write(encrypted)
        
        # Set file permissions
        os.chmod(file_path, 0o600)
        return file_path
    
    def retrieve_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve and decrypt session data"""
        file_path = self.base_dir / f"{session_id}.encrypted"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted = self.cipher.decrypt(encrypted_data)
            session_data = json.loads(decrypted.decode())
            
            # Check expiration
            if time.time() > session_data['expiry']:
                self._secure_delete(file_path)
                return None
            
            return session_data['data']
        
        except Exception as e:
            # If decryption fails, remove file
            self._secure_delete(file_path)
            return None
    
    def _secure_delete(self, file_path: Path) -> None:
        """Securely delete file by overwriting"""
        if file_path.exists():
            # Overwrite with random data
            file_size = file_path.stat().st_size
            with open(file_path, 'r+b') as f:
                f.write(os.urandom(file_size))
                f.flush()
                os.fsync(f.fileno())
            
            # Delete file
            file_path.unlink()
    
    def cleanup_expired(self) -> int:
        """Clean up expired session files"""
        cleaned = 0
        current_time = time.time()
        
        for file_path in self.base_dir.glob("*.encrypted"):
            try:
                with open(file_path, 'rb') as f:
                    encrypted_data = f.read()
                
                decrypted = self.cipher.decrypt(encrypted_data)
                session_data = json.loads(decrypted.decode())
                
                if current_time > session_data['expiry']:
                    self._secure_delete(file_path)
                    cleaned += 1
            
            except Exception:
                # If file is corrupted, delete it
                self._secure_delete(file_path)
                cleaned += 1
        
        return cleaned
    
    def _start_cleanup_scheduler(self):
        """Start background cleanup scheduler"""
        schedule.every(30).minutes.do(self.cleanup_expired)
        
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)
        
        cleanup_thread = threading.Thread(target=run_scheduler, daemon=True)
        cleanup_thread.start()
```

## Deployment Recommendations

### Development Environment
**Recommended**: **Containerized Sandbox**
- Easy debugging and development
- Complete isolation
- Simple cleanup and reset

### Testing Environment  
**Recommended**: **Temporary Encrypted Storage**
- Maintains session state for testing
- Automatic cleanup with audit capabilities
- Good balance of security and functionality

### Production Environment
**Recommended**: **In-Memory Encrypted Sandbox**
- Highest performance
- HIPAA compliance ready
- No persistent sensitive data

### High-Security Production
**Recommended**: **Secure Enclave** (when available)
- Maximum security assurance
- Hardware-level protection
- Compliance with strictest medical data requirements

## Security Considerations

### General Security Practices
1. **Key Management**: Use secure key derivation and storage
2. **Access Controls**: Implement proper authentication and authorization
3. **Audit Logging**: Log all sensitive data access (without logging the data itself)
4. **Network Security**: Use TLS for all communications
5. **Regular Cleanup**: Implement automatic cleanup policies
6. **Memory Management**: Overwrite sensitive data in memory when possible

### Medical Data Compliance
1. **HIPAA Requirements**: Ensure encryption at rest and in transit
2. **Data Minimization**: Store only necessary information
3. **Access Logging**: Track all access to medical data
4. **Retention Policies**: Implement automatic data expiration
5. **Breach Notification**: Plan for security incident response

### Implementation Checklist
- [ ] Choose appropriate sandbox approach for environment
- [ ] Implement encryption for sensitive data
- [ ] Configure automatic cleanup policies
- [ ] Set up monitoring and alerting
- [ ] Test security measures and cleanup procedures
- [ ] Document security procedures and incident response
- [ ] Regular security audits and updates

This comprehensive guide provides the foundation for implementing secure sandbox environments that protect sensitive medical data while maintaining the development and operational flexibility needed for the TN Staging System.