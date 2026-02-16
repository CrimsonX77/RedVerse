"""
Aurora Archive - Steganography Module
Embeds and extracts member data from card images using LSB steganography

Python 3.10+
Dependencies: Pillow, cryptography (optional for encryption)
"""

import json
import hashlib
from PIL import Image
from typing import Dict, Optional, Tuple
from pathlib import Path

card_image_path = Path("Desktop/Authunder/test_card_embedded.png")


class SteganographyError(Exception):
    """Base exception for steganography operations"""
    pass


class InsufficientCapacityError(SteganographyError):
    """Raised when image cannot hold the data"""
    pass


class CorruptedDataError(SteganographyError):
    """Raised when extracted data is corrupted"""
    pass


class CardSteganography:
    """
    LSB (Least Significant Bit) Steganography for Aurora Archive cards
    
    Embeds member data in card images by modifying the least significant bit
    of RGB color channels. Changes are imperceptible to human eyes.
    """
    
    # Magic header to identify Aurora cards (ASCII "AURORA")
    MAGIC_HEADER = "415552524152"  # Hex for "AURORA"
    
    # Embed in first N pixels for fast extraction (100x100 = 30KB capacity)
    EMBED_REGION_SIZE = 100
    
    def __init__(self, use_encryption: bool = False):
        """
        Initialize steganography system
        
        Args:
            use_encryption: If True, encrypt data before embedding (requires cryptography lib)
        """
        self.use_encryption = use_encryption
        self.cipher = None
        
        if use_encryption:
            try:
                from cryptography.fernet import Fernet
                self.cipher = Fernet(Fernet.generate_key())
            except ImportError:
                print("Warning: Encryption requires 'cryptography' package")
                print("Install with: pip install cryptography")
                self.use_encryption = False
                self.cipher = None
    
    def embed_member_data(
        self, 
        card_image_path: str = ["Desktop/Authunder/test_card.png"],
        member_data: Dict = {},
        output_path: Optional[str] = None,
        region_only: bool = True
    ) -> str:
        """
        Embed member data into a card image
        
        Args:
            card_image_path: Path to source card image
            member_data: Dictionary containing member information
            output_path: Where to save modified image (default: auto-generate)
            region_only: If True, only embed in top-left region for speed
            
        Returns:
            Path to the output image with embedded data
            
        Raises:
            InsufficientCapacityError: If image too small for data
            SteganographyError: If embedding fails
        """
        try:
            # Load image
            img = Image.open(card_image_path).convert('RGB')
            pixels = img.load()
            width, height = img.size
            
            # Prepare data
            json_data = json.dumps(member_data, separators=(',', ':'))
            
            # Add checksum for corruption detection
            checksum = hashlib.md5(json_data.encode()).hexdigest()[:8]
            
            # Build full payload: MAGIC + LENGTH + CHECKSUM + DATA
            full_data = f"{self.MAGIC_HEADER}{checksum}{json_data}"
            
            # Optional encryption
            if self.use_encryption:
                full_data = self._encrypt(full_data)
            
            # Convert to binary
            binary_data = ''.join(format(ord(char), '08b') for char in full_data)
            data_length = len(binary_data)
            
            # Add 32-bit length header
            length_header = format(len(json_data), '032b')
            full_binary = length_header + binary_data
            
            # Check capacity
            max_region_width = min(self.EMBED_REGION_SIZE, width)
            max_region_height = min(self.EMBED_REGION_SIZE, height)
            
            if region_only:
                available_bits = max_region_width * max_region_height * 3
            else:
                available_bits = width * height * 3
            
            if len(full_binary) > available_bits:
                raise InsufficientCapacityError(
                    f"Data requires {len(full_binary)} bits but only {available_bits} available"
                )
            
            # Embed data
            data_index = 0
            embed_height = max_region_height if region_only else height
            embed_width = max_region_width if region_only else width
            
            for y in range(embed_height):
                for x in range(embed_width):
                    if data_index >= len(full_binary):
                        break
                    
                    r, g, b = pixels[x, y]
                    
                    # Modify LSB of each channel
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
            
            # Save image
            if output_path is None:
                output_path = self._generate_output_path(card_image_path)
            
            # Must save as PNG - JPEG compression destroys LSB data
            if not output_path.lower().endswith('.png'):
                output_path += '.png'
            
            img.save(output_path, 'PNG', optimize=False)
            
            return output_path
            
        except Exception as e:
            raise SteganographyError(f"Failed to embed data: {str(e)}")
    
    def extract_member_data(
        self, 
        card_image_path: str,
        region_only: bool = True,
        verify_checksum: bool = True
    ) -> Dict:
        """
        Extract member data from a card image
        
        Args:
            card_image_path: Path to card image with embedded data
            region_only: If True, only read from top-left region
            verify_checksum: If True, verify data integrity
            
        Returns:
            Dictionary containing extracted member data
            
        Raises:
            CorruptedDataError: If data is corrupted or invalid
            SteganographyError: If extraction fails
        """
        try:
            # Load image
            img = Image.open(card_image_path).convert('RGB')
            pixels = img.load()
            width, height = img.size
            
            # Determine extraction region
            max_region_width = min(self.EMBED_REGION_SIZE, width)
            max_region_height = min(self.EMBED_REGION_SIZE, height)
            
            extract_height = max_region_height if region_only else height
            extract_width = max_region_width if region_only else width
            
            # Extract binary data
            binary_data = ''
            for y in range(extract_height):
                for x in range(extract_width):
                    r, g, b = pixels[x, y]
                    
                    # Extract LSB from each channel
                    binary_data += str(r & 1)
                    binary_data += str(g & 1)
                    binary_data += str(b & 1)
            
            # Read length header (first 32 bits)
            if len(binary_data) < 32:
                raise CorruptedDataError("Insufficient data in image")
            
            data_length = int(binary_data[:32], 2)
            
            # Calculate expected bits (length header + magic + checksum + data)
            # Magic = 12 chars, Checksum = 8 chars, Data = data_length chars
            expected_chars = 12 + 8 + data_length
            expected_bits = expected_chars * 8
            total_bits_needed = 32 + expected_bits
            
            if len(binary_data) < total_bits_needed:
                raise CorruptedDataError("Image does not contain complete data")
            
            # Extract full payload
            payload_binary = binary_data[32:total_bits_needed]
            
            # Convert binary to text
            payload = ''
            for i in range(0, len(payload_binary), 8):
                byte = payload_binary[i:i+8]
                if len(byte) == 8:
                    payload += chr(int(byte, 2))
            
            # Optional decryption
            if self.use_encryption:
                payload = self._decrypt(payload)
            
            # Verify magic header
            if not payload.startswith(self.MAGIC_HEADER):
                raise CorruptedDataError("Invalid magic header - not an Aurora card or data corrupted")
            
            # Extract components
            magic = payload[:12]
            checksum = payload[12:20]
            json_data = payload[20:]
            
            # Verify checksum
            if verify_checksum:
                computed_checksum = hashlib.md5(json_data.encode()).hexdigest()[:8]
                if checksum != computed_checksum:
                    raise CorruptedDataError(
                        f"Checksum mismatch - data corrupted (expected {checksum}, got {computed_checksum})"
                    )
            
            # Parse JSON
            member_data = json.loads(json_data)
            
            return member_data
            
        except json.JSONDecodeError as e:
            raise CorruptedDataError(f"Invalid JSON data: {str(e)}")
        except Exception as e:
            if isinstance(e, (CorruptedDataError, SteganographyError)):
                raise
            raise SteganographyError(f"Failed to extract data: {str(e)}")
    
    def verify_card(self, card_image_path: str) -> bool:
        """
        Check if an image contains valid Aurora card data
        
        Args:
            card_image_path: Path to image to verify
            
        Returns:
            True if valid Aurora card, False otherwise
        """
        try:
            self.extract_member_data(card_image_path, verify_checksum=True)
            return True
        except (CorruptedDataError, SteganographyError):
            return False
    
    def get_capacity(self, image_path: str, region_only: bool = True) -> Tuple[int, int]:
        """
        Calculate available capacity in an image
        
        Args:
            image_path: Path to image
            region_only: If True, calculate for embed region only
            
        Returns:
            Tuple of (available_bytes, available_chars)
        """
        img = Image.open(image_path)
        width, height = img.size
        
        if region_only:
            max_width = min(self.EMBED_REGION_SIZE, width)
            max_height = min(self.EMBED_REGION_SIZE, height)
            available_bits = max_width * max_height * 3
        else:
            available_bits = width * height * 3
        
        # Subtract length header (32 bits)
        available_bits -= 32
        
        available_bytes = available_bits // 8
        available_chars = available_bytes  # Assuming ASCII/UTF-8
        
        return (available_bytes, available_chars)
    
    def _generate_output_path(self, input_path: str) -> str:
        """Generate output filename for embedded image"""
        path = Path(input_path)
        stem = path.stem
        return str(path.parent / f"{stem}_embedded.png")
    
    def _encrypt(self, data: str) -> str:
        """Encrypt data before embedding"""
        if not self.use_encryption:
            return data
        encrypted = self.cipher.encrypt(data.encode())
        return encrypted.decode('latin-1')  # Preserve binary data as string
    
    def _decrypt(self, data: str) -> str:
        """Decrypt data after extraction"""
        if not self.use_encryption:
            return data
        decrypted = self.cipher.decrypt(data.encode('latin-1'))
        return decrypted.decode()
    
    # Aliases for compatibility with aurora_pyqt6_main.py
    def embed_data(self, card_image_path: str, member_data: Dict, 
                   output_path: Optional[str] = None, overwrite: bool = False) -> str:
        """
        Alias for embed_member_data() - compatible with Aurora main app
        
        Args:
            card_image_path: Path to source card image
            member_data: Dictionary containing member/card information
            output_path: Where to save modified image (default: auto-generate)
            overwrite: If True, overwrite the original file
            
        Returns:
            Path to the output image with embedded data
        """
        if overwrite:
            output_path = card_image_path
        return self.embed_member_data(card_image_path, member_data, output_path)
    
    def extract_data(self, card_image_path: str, verify_checksum: bool = True) -> Dict:
        """
        Alias for extract_member_data() - compatible with Aurora main app
        
        Args:
            card_image_path: Path to card image with embedded data
            verify_checksum: If True, verify data integrity
            
        Returns:
            Dictionary containing extracted data
        """
        return self.extract_member_data(card_image_path, verify_checksum=verify_checksum)


# Convenience functions
def embed_card_data(image_path: str, member_data: Dict, output_path: Optional[str] = None) -> str:
    """
    Quick function to embed member data in a card image
    
    Args:
        image_path: Source card image
        member_data: Member information dict
        output_path: Where to save (optional)
        
    Returns:
        Path to output image
    """
    stego = CardSteganography()
    return stego.embed_member_data(image_path, member_data, output_path)


def extract_card_data(image_path: str) -> Dict:
    """
    Quick function to extract member data from a card image
    
    Args:
        image_path: Card image with embedded data
        
    Returns:
        Member data dictionary
    """
    stego = CardSteganography()
    return stego.extract_member_data(image_path)


def is_aurora_card(image_path: str) -> bool:
    """
    Check if image is a valid Aurora card
    
    Args:
        image_path: Path to image
        
    Returns:
        True if valid Aurora card
    """
    stego = CardSteganography()
    return stego.verify_card(image_path)


# Example usage and testing
if __name__ == '__main__':
    # Example member data
    example_member = {
        "card_id": "aurora_001_crimson",
        "member_id": "m_1847392",
        "name": "Crimson",
        "tier": "Premium",
        "email": "crimsonmythx7@gmail.com",
        "created": "2025-11-07T19:32:00Z",
        "subscription": {
            "status": "active",
            "next_billing": "2025-12-07"
        },
        "database_pointer": "members.jsonl:line_47"
    }
    
    print("Aurora Archive - Steganography Module Test")
    print("=" * 50)
    
    # Test with a sample image (you'll need to provide an actual image path)
    test_image = "home/crimson/Desktop/Authunder/test_card_embedded22.png"  # Replace with your card image path
    
    try:
        # Create steganography instance
        stego = CardSteganography()
        
        # Check capacity
        available_bytes, available_chars = stego.get_capacity(test_image)
        print(f"Image capacity: {available_bytes} bytes ({available_chars} characters)")
        
        # Embed data
        print(f"\nEmbedding member data into {test_image}...")
        output = stego.embed_member_data(test_image, example_member)
        print(f"✓ Data embedded successfully: {output}")
        
        # Extract data
        print(f"\nExtracting data from {output}...")
        extracted = stego.extract_member_data(output)
        print(f"✓ Data extracted successfully:")
        print(json.dumps(extracted, indent=2))
        
        # Verify
        print(f"\nVerifying card...")
        is_valid = stego.verify_card(output)
        print(f"✓ Card valid: {is_valid}")
        
        # Compare
        if extracted == example_member:
            print("\n✓ SUCCESS: Extracted data matches original!")
        else:
            print("\n✗ WARNING: Data mismatch")
            
    except FileNotFoundError:
        print(f"\n✗ Error: Test image '{test_image}' not found")
        print("Create a test PNG image or update the test_image path")
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")