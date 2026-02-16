"""
API Configuration Manager
Secure storage and management of API keys with encryption
"""

import os
import json
import base64
from pathlib import Path
from typing import Dict, List, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class APIConfigManager:
    """Manages API keys with encryption and persistence"""
    
    # Supported API backends
    SUPPORTED_APIS = {
        'grok': {
            'name': 'Grok AI (xAI)',
            'url_key': 'base_url',
            'api_key_name': 'API Key',
            'default_url': 'https://api.x.ai/v1',
            'test_endpoint': '/models',
            'requires_key': True
        },
        'stable_diffusion': {
            'name': 'Stable Diffusion WebUI',
            'url_key': 'url',
            'api_key_name': None,  # No API key needed for local SD
            'default_url': 'http://localhost:7860',
            'test_endpoint': '/sdapi/v1/sd-models',
            'requires_key': False
        },
        'openai': {
            'name': 'OpenAI DALL-E',
            'url_key': 'base_url',
            'api_key_name': 'API Key',
            'default_url': 'https://api.openai.com/v1',
            'test_endpoint': '/models',
            'requires_key': True
        },
        'stability': {
            'name': 'Stability AI',
            'url_key': 'base_url',
            'api_key_name': 'API Key',
            'default_url': 'https://api.stability.ai',
            'test_endpoint': '/v1/engines/list',
            'requires_key': True
        },
        'midjourney': {
            'name': 'Midjourney API',
            'url_key': 'base_url',
            'api_key_name': 'API Key',
            'default_url': 'https://api.midjourney.com',
            'test_endpoint': '/info',
            'requires_key': True
        }
    }
    
    def __init__(self, config_dir: str = 'config'):
        """
        Initialize API config manager
        
        Args:
            config_dir: Directory to store encrypted config
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.config_dir / 'api_config.enc'
        self.key_file = self.config_dir / '.key'
        
        # Generate or load encryption key
        self.cipher = self._get_cipher()
        
        # Load existing config
        self.config = self._load_config()
        
    def _get_cipher(self) -> Fernet:
        """Get or create encryption cipher"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate new key from machine-specific data
            machine_id = self._get_machine_id()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'crimson_collective_aurora',
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
            
            with open(self.key_file, 'wb') as f:
                f.write(key)
            
            # Restrict file permissions (Unix)
            try:
                os.chmod(self.key_file, 0o600)
            except:
                pass
        
        return Fernet(key)
    
    def _get_machine_id(self) -> str:
        """Get machine-specific identifier"""
        try:
            # Try to get machine ID
            if Path('/etc/machine-id').exists():
                return Path('/etc/machine-id').read_text().strip()
            elif Path('/var/lib/dbus/machine-id').exists():
                return Path('/var/lib/dbus/machine-id').read_text().strip()
            else:
                # Fallback to user home directory path
                return str(Path.home())
        except:
            return 'default_machine_id'
    
    def _load_config(self) -> Dict:
        """Load encrypted config from disk"""
        if not self.config_file.exists():
            return {
                'apis': {},
                'last_used': None,
                'auto_connect': []
            }
        
        try:
            with open(self.config_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            print(f"Warning: Could not load config: {e}")
            return {
                'apis': {},
                'last_used': None,
                'auto_connect': []
            }
    
    def _save_config(self):
        """Save encrypted config to disk"""
        try:
            config_json = json.dumps(self.config, indent=2)
            encrypted_data = self.cipher.encrypt(config_json.encode())
            
            with open(self.config_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Restrict file permissions
            try:
                os.chmod(self.config_file, 0o600)
            except:
                pass
                
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def add_api(self, api_type: str, url: str, api_key: Optional[str] = None) -> bool:
        """
        Add or update API configuration
        
        Args:
            api_type: Type of API (grok, stable_diffusion, etc.)
            url: API base URL
            api_key: API key (if required)
            
        Returns:
            True if successful
        """
        if api_type not in self.SUPPORTED_APIS:
            return False
        
        api_info = self.SUPPORTED_APIS[api_type]
        
        # Validate required fields
        if api_info['requires_key'] and not api_key:
            return False
        
        # Store config
        self.config['apis'][api_type] = {
            'url': url,
            'api_key': api_key if api_key else None,
            'added_at': str(Path(self.config_file).stat().st_mtime if self.config_file.exists() else 0),
            'verified': False,
            'last_used': None
        }
        
        self._save_config()
        return True
    
    def remove_api(self, api_type: str):
        """Remove API configuration"""
        if api_type in self.config['apis']:
            del self.config['apis'][api_type]
            
            # Remove from auto-connect
            if api_type in self.config['auto_connect']:
                self.config['auto_connect'].remove(api_type)
            
            self._save_config()
    
    def get_api(self, api_type: str) -> Optional[Dict]:
        """Get API configuration"""
        return self.config['apis'].get(api_type)
    
    def get_all_apis(self) -> Dict[str, Dict]:
        """Get all configured APIs"""
        return self.config['apis'].copy()
    
    def mark_verified(self, api_type: str, verified: bool = True):
        """Mark API as verified after successful connection"""
        if api_type in self.config['apis']:
            self.config['apis'][api_type]['verified'] = verified
            self._save_config()
    
    def set_auto_connect(self, api_type: str, auto: bool = True):
        """Set API to auto-connect on startup"""
        if api_type not in self.config['apis']:
            return
        
        if auto and api_type not in self.config['auto_connect']:
            self.config['auto_connect'].append(api_type)
        elif not auto and api_type in self.config['auto_connect']:
            self.config['auto_connect'].remove(api_type)
        
        self._save_config()
    
    def get_auto_connect_apis(self) -> List[str]:
        """Get list of APIs set to auto-connect"""
        return self.config['auto_connect'].copy()
    
    def set_last_used(self, api_type: str):
        """Update last used API"""
        if api_type in self.config['apis']:
            import time
            self.config['apis'][api_type]['last_used'] = time.time()
            self.config['last_used'] = api_type
            self._save_config()
    
    def get_last_used(self) -> Optional[str]:
        """Get last used API type"""
        return self.config.get('last_used')
    
    def export_to_env(self, api_type: str, env_file: str = '.env'):
        """
        Export API config to .env file
        
        Args:
            api_type: API type to export
            env_file: Path to .env file
        """
        api_config = self.get_api(api_type)
        if not api_config:
            return
        
        api_info = self.SUPPORTED_APIS[api_type]
        
        env_path = Path(env_file)
        
        # Read existing .env
        if env_path.exists():
            lines = env_path.read_text().split('\n')
        else:
            lines = []
        
        # Update or add variables
        if api_type == 'grok':
            self._update_env_var(lines, 'GROK_API_KEY', api_config.get('api_key', ''))
            self._update_env_var(lines, 'GROK_BASE_URL', api_config.get('url', ''))
        elif api_type == 'stable_diffusion':
            self._update_env_var(lines, 'STABLE_DIFFUSION_URL', api_config.get('url', ''))
        elif api_type == 'openai':
            self._update_env_var(lines, 'OPENAI_API_KEY', api_config.get('api_key', ''))
            self._update_env_var(lines, 'OPENAI_BASE_URL', api_config.get('url', ''))
        elif api_type == 'stability':
            self._update_env_var(lines, 'STABILITY_API_KEY', api_config.get('api_key', ''))
            self._update_env_var(lines, 'STABILITY_BASE_URL', api_config.get('url', ''))
        
        # Write back
        env_path.write_text('\n'.join(lines))
    
    def _update_env_var(self, lines: List[str], key: str, value: str):
        """Update or add environment variable in lines"""
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f'{key}='):
                lines[i] = f'{key}={value}'
                found = True
                break
        
        if not found:
            lines.append(f'{key}={value}')
