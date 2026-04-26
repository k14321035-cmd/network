import asyncio
import json
import base64
import os
import hmac
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
import httpx
import uvicorn
from datetime import datetime, timedelta
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tunnel.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Device API keys (in production, use a database)
DEVICE_KEYS = {
    "device_001": "your-secret-key-1",
    "device_002": "your-secret-key-2",
}

# Rate limiting: requests per minute per device
RATE_LIMITS = {
    "device_001": 100,  # 100 requests/minute
    "device_002": 50,   # 50 requests/minute
}

# In-memory rate limit tracking (use Redis in production)
rate_limit_cache = {}

# WebSocket connections (device_id -> WebSocket)
websocket_connections = {}

def is_rate_limited(device_id: str) -> bool:
    """Check if device has exceeded rate limit."""
    now = time.time()
    limit = RATE_LIMITS.get(device_id, 10)  # Default 10/minute
    
    if device_id not in rate_limit_cache:
        rate_limit_cache[device_id] = []
    
    # Clean old requests (older than 1 minute)
    rate_limit_cache[device_id] = [
        req_time for req_time in rate_limit_cache[device_id] 
        if now - req_time < 60
    ]
    
    # Check if under limit
    if len(rate_limit_cache[device_id]) >= limit:
        return True
    
    # Add current request
    rate_limit_cache[device_id].append(now)
    return False

@app.get("/health")
async def health():
    return {"status": "ok", "message": "local target reachable"}

# ------------- WebSocket Persistent Tunnel -------------
@app.websocket("/ws/analytics")
async def websocket_tunnel(websocket: WebSocket):
    """
    Persistent WebSocket tunnel disguised as analytics connection.
    Mobile clients maintain long-lived connections that appear as analytics traffic.
    """
    logger.info("New WebSocket connection attempt")
    await websocket.accept()
    
    device_id = None
    api_key = None
    
    try:
        # Initial handshake: receive device authentication
        auth_data = await websocket.receive_json()
        device_id = auth_data.get("device_id")
        encrypted_auth = auth_data.get("auth_token")
        
        logger.info(f"WebSocket connection attempt from device: {device_id}")
        
        if not device_id or not encrypted_auth:
            await websocket.send_json({"error": "missing_auth"})
            await websocket.close()
            return
        
        if device_id not in DEVICE_KEYS:
            logger.warning(f"WebSocket auth failed: invalid device {device_id}")
            await websocket.send_json({"error": "invalid_device"})
            await websocket.close()
            return
        
        api_key = DEVICE_KEYS[device_id]
        
        # Verify authentication token (encrypted timestamp)
        try:
            auth_payload = decrypt_message(encrypted_auth, api_key)
            auth_info = json.loads(auth_payload.decode())
            
            # Check timestamp is recent (within 5 minutes)
            timestamp = auth_info.get("timestamp", 0)
            current_time = time.time()
            logger.info(f"WebSocket auth timestamp check: received={timestamp}, current={current_time}, diff={current_time - timestamp}")
            if current_time - timestamp > 300:  # 5 minutes
                logger.warning(f"WebSocket auth expired for device: {device_id}")
                await websocket.send_json({"error": "auth_expired"})
                await websocket.close()
                return
                
        except Exception as e:
            logger.warning(f"WebSocket auth decryption failed: {e}")
            await websocket.send_json({"error": "auth_failed"})
            await websocket.close()
            return
        
        # Authentication successful
        websocket_connections[device_id] = websocket
        logger.info(f"WebSocket tunnel established for device: {device_id}")
        await websocket.send_json({"status": "connected", "session_id": base64.b64encode(os.urandom(8)).decode()})
        
        # Main tunnel loop
        while True:
            try:
                # Receive encrypted request
                data = await websocket.receive_json()
                encrypted_msg = data.get("event_data")
                
                if not encrypted_msg:
                    continue
                
                # Check rate limiting
                if is_rate_limited(device_id):
                    logger.warning(f"WebSocket rate limit exceeded for device: {device_id}")
                    await websocket.send_json({"error": "rate_limited"})
                    continue
                
                # Decrypt request
                payload = decrypt_message(encrypted_msg, api_key)
                envelope = json.loads(payload.decode())
                
                logger.info(f"WebSocket request: {envelope['method']} {envelope['url']}")
                
                if envelope.get("type") != "http":
                    await websocket.send_json({"error": "unsupported"})
                    continue
                
                # Execute outbound request
                async with httpx.AsyncClient() as client:
                    logger.info(f"WebSocket outbound: {envelope['method']} {envelope['url']}")
                    resp = await client.request(
                        method=envelope["method"],
                        url=envelope["url"],
                        headers=envelope.get("headers", {}),
                        content=base64.b64decode(envelope.get("body", ""))
                    )
                    logger.info(f"WebSocket response: {resp.status_code} ({len(resp.content)} bytes)")
                
                # Prepare and encrypt response
                resp_env = {
                    "status": resp.status_code,
                    "headers": dict(resp.headers),
                    "body": base64.b64encode(resp.content).decode()
                }
                
                enc_resp = encrypt_message(json.dumps(resp_env).encode(), api_key)
                
                # Send encrypted response
                await websocket.send_json({
                    "success": True,
                    "event_id": base64.b64encode(os.urandom(8)).decode(),
                    "response": enc_resp
                })
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {device_id}")
                break
            except Exception as e:
                logger.error(f"WebSocket error for {device_id}: {e}")
                try:
                    await websocket.send_json({"error": "internal_error", "detail": str(e)})
                except:
                    break
    
    except Exception as e:
        logger.error(f"WebSocket setup error: {e}")
    
    finally:
        if device_id and device_id in websocket_connections:
            del websocket_connections[device_id]

# ------------- ChaCha20-Poly1305 Encryption (AEAD) -------------
def derive_key(api_key: str, nonce_salt: str) -> bytes:
    """Derive a 32-byte key from API key + salt using PBKDF2HMAC."""
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=nonce_salt.encode(), iterations=100000)
    return kdf.derive(api_key.encode())

def encrypt_message(payload: bytes, api_key: str) -> str:
    """Encrypt payload using ChaCha20-Poly1305 with HMAC. Return base64 of nonce+ciphertext+tag."""
    nonce = os.urandom(12)  # 12 bytes for ChaCha20
    nonce_salt = base64.b64encode(nonce).decode()[:16]  # Use part of nonce as salt
    key = derive_key(api_key, nonce_salt)
    
    cipher = ChaCha20Poly1305(key)
    ciphertext = cipher.encrypt(nonce, payload, associated_data=None)
    
    # Package: nonce (12B) + ciphertext+tag (variable)
    package = nonce + ciphertext
    return base64.b64encode(package).decode()

def decrypt_message(encrypted_b64: str, api_key: str) -> bytes:
    """Decrypt ChaCha20-Poly1305 encrypted message."""
    package = base64.b64decode(encrypted_b64)
    nonce = package[:12]
    ciphertext_with_tag = package[12:]
    
    nonce_salt = base64.b64encode(nonce).decode()[:16]
    key = derive_key(api_key, nonce_salt)
    
    cipher = ChaCha20Poly1305(key)
    return cipher.decrypt(nonce, ciphertext_with_tag, associated_data=None)

# ------------- Main proxy endpoint (disguised as analytics) -------------
@app.post("/api/analytics/track")
async def tunnel(request: Request):
    """
    Mobile clients send encrypted requests disguised as analytics events.
    To network observers (ISP/firewall), this looks like ad/analytics traffic.
    """
    try:
        data = await request.json()
        
        # Extract device ID and encrypted envelope
        device_id = data.get("device_id")
        encrypted_msg = data.get("event_data")  # Disguised as event payload
        
        logger.info(f"Analytics request from device: {device_id}")
        
        if not device_id or not encrypted_msg:
            logger.warning("Missing device_id or event_data in request")
            raise HTTPException(status_code=400, detail="Missing device_id or event_data")
        
        if device_id not in DEVICE_KEYS:
            logger.warning(f"Invalid device ID: {device_id}")
            raise HTTPException(status_code=403, detail="Invalid device")
        
        # Check rate limiting
        if is_rate_limited(device_id):
            logger.warning(f"Rate limit exceeded for device: {device_id}")
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        api_key = DEVICE_KEYS[device_id]
        
        # Decrypt the HTTP request envelope
        payload = decrypt_message(encrypted_msg, api_key)
        envelope = json.loads(payload.decode())
        
        logger.info(f"Decrypted request: {envelope['method']} {envelope['url']}")
        
        if envelope.get("type") != "http":
            logger.warning(f"Unsupported request type: {envelope.get('type')}")
            return {"error": "unsupported"}
        
        # Execute the outbound HTTP request
        async with httpx.AsyncClient() as client:
            logger.info(f"Making outbound request: {envelope['method']} {envelope['url']}")
            resp = await client.request(
                method=envelope["method"],
                url=envelope["url"],
                headers=envelope.get("headers", {}),
                content=base64.b64decode(envelope.get("body", ""))
            )
            logger.info(f"Outbound response: {resp.status_code} ({len(resp.content)} bytes)")
        
        # Prepare response envelope
        resp_env = {
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "body": base64.b64encode(resp.content).decode()
        }
        
        # Encrypt response
        enc_resp = encrypt_message(json.dumps(resp_env).encode(), api_key)
        
        logger.info(f"Encrypted response sent to device: {device_id}")
        
        # Return disguised as analytics response
        return {
            "success": True,
            "event_id": base64.b64encode(os.urandom(8)).decode(),
            "response": enc_resp  # Hidden inside analytics response
        }
    
    except Exception as exc:
        logger.error(f"Tunnel error: {str(exc)}")
        return {"error": "internal_error", "detail": str(exc)}

def main():
    host = os.getenv("PROXY_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("PROXY_SERVER_PORT", "8443"))
    logger.info(f"Starting server on {host}:{port}")
    try:
        uvicorn.run("proxy_server:app", host=host, port=port, log_level="error")
    except OSError as exc:
        logger.error(f"Failed to bind server to {host}:{port} - {exc}")
        raise

if __name__ == "__main__":
    main()
