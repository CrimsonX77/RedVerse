"""
Aurora Archive - Mutable Steganography System
Advanced card data management with overwrite and async edit capabilities

Python 3.10+
Dependencies: Pillow, aiofiles
"""

import json
import hashlib
import asyncio
import aiofiles
from PIL import Image
from typing import Dict, Optional, Callable, Any
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager


class CardLockError(Exception):
    """Raised when attempting to modify a locked card"""
    pass


class MutableCardSteganography:
    """
    Advanced steganography system with:
    - Overwrite capability (embed new data regardless of existing data)
    - Async read-modify-write operations
    - Card locking for concurrent access control
    - Edit history tracking
    """
    
    MAGIC_HEADER = "415552524152"  # "AURORA" in hex
    EMBED_REGION_SIZE = 100
    VERSION = "1.0"
    
    def __init__(self):
        self._locks = {}  # Card path -> asyncio.Lock
        self._edit_history = {}  # Card path -> list of edits
    
    # ============================================
    # BASIC OPERATIONS (Sync)
    # ============================================
    
    def embed_data(
        self,
        image_path: str,
        data: Dict,
        output_path: Optional[str] = None,
        force_overwrite: bool = True
    ) -> str:
        """
        Embed data into image, overwriting any existing data
        
        Args:
            image_path: Source image path
            data: Dictionary to embed
            output_path: Where to save (None = overwrite source)
            force_overwrite: If True, ignore existing data and overwrite
            
        Returns:
            Path to output image
        """
        # Check if data exists and handle accordingly
        has_existing_data = self.has_embedded_data(image_path)
        
        if has_existing_data and not force_overwrite:
            raise ValueError(
                f"Image already contains embedded data. Use force_overwrite=True or update_data() instead"
            )
        
        # Load image (fresh, ignoring any existing LSB data)
        img = Image.open(image_path).convert('RGB')
        pixels = img.load()
        width, height = img.size
        
        # Add metadata
        data_with_meta = {
            **data,
            "_aurora_meta": {
                "version": self.VERSION,
                "embedded_at": datetime.utcnow().isoformat(),
                "edit_count": 0
            }
        }
        
        # Prepare payload
        json_data = json.dumps(data_with_meta, separators=(',', ':'))
        checksum = hashlib.md5(json_data.encode()).hexdigest()[:8]
        full_data = f"{self.MAGIC_HEADER}{checksum}{json_data}"
        
        # Convert to binary
        binary_data = ''.join(format(ord(char), '08b') for char in full_data)
        length_header = format(len(json_data), '032b')
        full_binary = length_header + binary_data
        
        # Check capacity
        max_region_width = min(self.EMBED_REGION_SIZE, width)
        max_region_height = min(self.EMBED_REGION_SIZE, height)
        available_bits = max_region_width * max_region_height * 3
        
        if len(full_binary) > available_bits:
            raise ValueError(
                f"Data too large: {len(full_binary)} bits needed, {available_bits} available"
            )
        
        # CRITICAL: Clear the entire embed region first
        # This ensures old data doesn't bleed through
        for y in range(max_region_height):
            for x in range(max_region_width):
                r, g, b = pixels[x, y]
                # Clear LSBs (set all to 0)
                r = r & 0xFE
                g = g & 0xFE
                b = b & 0xFE
                pixels[x, y] = (r, g, b)
        
        # Embed new data
        data_index = 0
        for y in range(max_region_height):
            for x in range(max_region_width):
                if data_index >= len(full_binary):
                    break
                
                r, g, b = pixels[x, y]
                
                # Set LSB to data bits
                if data_index < len(full_binary):
                    r = (r & 0xFE) | int(full_binary[data_index])
                    data_index += 1
                if data_index < len(full_binary):
                    g = (g & 0xFE) | int(full_binary[data_index])
                    data_index += 1
                if data_index < len(full_binary):
                    b = (b & 0xFE) | int(full_binary[data_index])
                    data_index += 1
                
                pixels[x, y] = (r, g, b)
            
            if data_index >= len(full_binary):
                break
        
        # Save
        if output_path is None:
            output_path = image_path
        
        if not output_path.lower().endswith('.png'):
            output_path += '.png'
        
        img.save(output_path, 'PNG', optimize=False)
        
        return output_path
    
    def extract_data(self, image_path: str) -> Dict:
        """
        Extract embedded data from image
        
        Args:
            image_path: Path to card image
            
        Returns:
            Dictionary of embedded data (without _aurora_meta)
        """
        img = Image.open(image_path).convert('RGB')
        pixels = img.load()
        width, height = img.size
        
        max_region_width = min(self.EMBED_REGION_SIZE, width)
        max_region_height = min(self.EMBED_REGION_SIZE, height)
        
        # Extract binary data
        binary_data = ''
        for y in range(max_region_height):
            for x in range(max_region_width):
                r, g, b = pixels[x, y]
                binary_data += str(r & 1)
                binary_data += str(g & 1)
                binary_data += str(b & 1)
        
        # Read length header
        if len(binary_data) < 32:
            raise ValueError("No embedded data found")
        
        data_length = int(binary_data[:32], 2)
        
        # Extract payload
        expected_chars = 12 + 8 + data_length  # magic + checksum + data
        expected_bits = expected_chars * 8
        total_bits = 32 + expected_bits
        
        if len(binary_data) < total_bits:
            raise ValueError("Incomplete embedded data")
        
        payload_binary = binary_data[32:total_bits]
        
        # Convert to text
        payload = ''
        for i in range(0, len(payload_binary), 8):
            byte = payload_binary[i:i+8]
            if len(byte) == 8:
                payload += chr(int(byte, 2))
        
        # Verify magic header
        if not payload.startswith(self.MAGIC_HEADER):
            raise ValueError("Invalid Aurora card - magic header mismatch")
        
        # Extract components
        checksum = payload[12:20]
        json_data = payload[20:]
        
        # Verify checksum
        computed_checksum = hashlib.md5(json_data.encode()).hexdigest()[:8]
        if checksum != computed_checksum:
            raise ValueError(f"Data corrupted - checksum mismatch")
        
        # Parse JSON
        full_data = json.loads(json_data)
        
        # Return data without metadata
        return {k: v for k, v in full_data.items() if k != '_aurora_meta'}
    
    def has_embedded_data(self, image_path: str) -> bool:
        """Check if image contains valid Aurora data"""
        try:
            self.extract_data(image_path)
            return True
        except (ValueError, json.JSONDecodeError):
            return False
    
    def get_metadata(self, image_path: str) -> Optional[Dict]:
        """Get Aurora metadata from card"""
        try:
            img = Image.open(image_path).convert('RGB')
            pixels = img.load()
            width, height = img.size
            
            max_region_width = min(self.EMBED_REGION_SIZE, width)
            max_region_height = min(self.EMBED_REGION_SIZE, height)
            
            # Extract binary data
            binary_data = ''
            for y in range(max_region_height):
                for x in range(max_region_width):
                    r, g, b = pixels[x, y]
                    binary_data += str(r & 1)
                    binary_data += str(g & 1)
                    binary_data += str(b & 1)
            
            data_length = int(binary_data[:32], 2)
            expected_chars = 12 + 8 + data_length
            expected_bits = expected_chars * 8
            total_bits = 32 + expected_bits
            
            payload_binary = binary_data[32:total_bits]
            
            payload = ''
            for i in range(0, len(payload_binary), 8):
                byte = payload_binary[i:i+8]
                if len(byte) == 8:
                    payload += chr(int(byte, 2))
            
            json_data = payload[20:]
            full_data = json.loads(json_data)
            
            return full_data.get('_aurora_meta')
            
        except:
            return None
    
    # ============================================
    # ASYNC OPERATIONS
    # ============================================
    
    async def async_embed_data(
        self,
        image_path: str,
        data: Dict,
        output_path: Optional[str] = None,
        force_overwrite: bool = True
    ) -> str:
        """Async version of embed_data"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.embed_data,
            image_path,
            data,
            output_path,
            force_overwrite
        )
    
    async def async_extract_data(self, image_path: str) -> Dict:
        """Async version of extract_data"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.extract_data, image_path)
    
    @asynccontextmanager
    async def edit_card(self, image_path: str):
        """
        Context manager for safe concurrent card editing
        
        Usage:
            async with stego.edit_card("card.png") as data:
                data['tier'] = 'Premium'
                data['credits'] += 100
            # Data automatically saved when context exits
        """
        # Get or create lock for this card
        if image_path not in self._locks:
            self._locks[image_path] = asyncio.Lock()
        
        lock = self._locks[image_path]
        
        async with lock:
            # Load current data
            data = await self.async_extract_data(image_path)
            
            # Create editable wrapper
            editor = CardDataEditor(data, image_path, self)
            
            try:
                yield editor
                
                # Save changes if modified
                if editor.is_modified:
                    # Update edit count
                    metadata = self.get_metadata(image_path) or {}
                    edit_count = metadata.get('edit_count', 0) + 1
                    
                    data['_aurora_meta'] = {
                        "version": self.VERSION,
                        "embedded_at": metadata.get('embedded_at', datetime.utcnow().isoformat()),
                        "last_modified": datetime.utcnow().isoformat(),
                        "edit_count": edit_count
                    }
                    
                    # Save
                    await self.async_embed_data(
                        image_path,
                        editor.data,
                        output_path=image_path,
                        force_overwrite=True
                    )
                    
                    # Track edit history
                    if image_path not in self._edit_history:
                        self._edit_history[image_path] = []
                    
                    self._edit_history[image_path].append({
                        'timestamp': datetime.utcnow().isoformat(),
                        'changes': editor.changes
                    })
                    
            except Exception as e:
                # On error, don't save changes
                raise CardLockError(f"Failed to edit card: {str(e)}")
    
    async def update_fields(
        self,
        image_path: str,
        updates: Dict[str, Any]
    ) -> Dict:
        """
        Update specific fields in card data
        
        Args:
            image_path: Card to update
            updates: Dict of field -> new value
            
        Returns:
            Updated data
        """
        async with self.edit_card(image_path) as card:
            for key, value in updates.items():
                card[key] = value
            return card.data
    
    async def batch_update(
        self,
        updates: list[tuple[str, Dict]]
    ) -> list[Dict]:
        """
        Update multiple cards concurrently
        
        Args:
            updates: List of (image_path, updates_dict) tuples
            
        Returns:
            List of updated data dicts
        """
        tasks = [
            self.update_fields(image_path, update_dict)
            for image_path, update_dict in updates
        ]
        return await asyncio.gather(*tasks)
    
    def get_edit_history(self, image_path: str) -> list[Dict]:
        """Get edit history for a card"""
        return self._edit_history.get(image_path, [])


class CardDataEditor:
    """
    Wrapper for card data that tracks modifications
    Used internally by edit_card context manager
    """
    
    def __init__(self, data: Dict, image_path: str, stego: MutableCardSteganography):
        self.data = data.copy()
        self._original = data.copy()
        self._image_path = image_path
        self._stego = stego
        self.changes = []
    
    def __getitem__(self, key):
        return self.data[key]
    
    def __setitem__(self, key, value):
        old_value = self.data.get(key)
        self.data[key] = value
        if old_value != value:
            self.changes.append({
                'field': key,
                'old': old_value,
                'new': value
            })
    
    def __delitem__(self, key):
        if key in self.data:
            old_value = self.data[key]
            del self.data[key]
            self.changes.append({
                'field': key,
                'old': old_value,
                'new': None
            })
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def update(self, updates: Dict):
        """Update multiple fields at once"""
        for key, value in updates.items():
            self[key] = value
    
    @property
    def is_modified(self) -> bool:
        return len(self.changes) > 0


# Convenience functions
async def quick_embed(image_path: str, data: Dict) -> str:
    """Quick async embed"""
    stego = MutableCardSteganography()
    return await stego.async_embed_data(image_path, data)


async def quick_extract(image_path: str) -> Dict:
    """Quick async extract"""
    stego = MutableCardSteganography()
    return await stego.async_extract_data(image_path)


async def quick_update(image_path: str, updates: Dict) -> Dict:
    """Quick async update"""
    stego = MutableCardSteganography()
    return await stego.update_fields(image_path, updates)


# Example usage
if __name__ == '__main__':
    async def demo():
        print("Aurora Archive - Mutable Steganography Demo")
        print("=" * 50)
        
        stego = MutableCardSteganography()
        test_card = "test_card.png"
        
        # Initial embed
        print("\n1. Embedding initial data...")
        initial_data = {
            "card_id": "aurora_001",
            "name": "Crimson",
            "tier": "Standard",
            "credits": 100
        }
        
        try:
            await stego.async_embed_data(test_card, initial_data)
            print("✓ Initial data embedded")
            
            # Extract and display
            print("\n2. Extracting data...")
            extracted = await stego.async_extract_data(test_card)
            print(f"✓ Extracted: {json.dumps(extracted, indent=2)}")
            
            # Edit using context manager
            print("\n3. Editing card data...")
            async with stego.edit_card(test_card) as card:
                card['tier'] = 'Premium'
                card['credits'] = 500
                card['upgraded_at'] = datetime.utcnow().isoformat()
            
            print("✓ Card updated")
            
            # Verify changes
            print("\n4. Verifying changes...")
            updated = await stego.async_extract_data(test_card)
            print(f"✓ New data: {json.dumps(updated, indent=2)}")
            
            # Show metadata
            print("\n5. Card metadata:")
            meta = stego.get_metadata(test_card)
            if meta:
                print(f"✓ Version: {meta.get('version')}")
                print(f"✓ Edit count: {meta.get('edit_count')}")
                print(f"✓ Last modified: {meta.get('last_modified')}")
            
            # Show edit history
            print("\n6. Edit history:")
            history = stego.get_edit_history(test_card)
            for i, edit in enumerate(history, 1):
                print(f"  Edit {i} at {edit['timestamp']}:")
                for change in edit['changes']:
                    print(f"    - {change['field']}: {change['old']} → {change['new']}")
            
            print("\n✓ Demo complete!")
            
        except FileNotFoundError:
            print(f"\n✗ Test card '{test_card}' not found")
            print("Create a test PNG image first")
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
    
    # Run demo
    asyncio.run(demo())