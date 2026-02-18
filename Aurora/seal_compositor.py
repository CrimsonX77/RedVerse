"""
Aurora Archive - RedSeal Compositor
Embeds account data into RedSeal.png, then composites onto card bottom-left corner

Process:
1. Resize RedSeal.png to 100x100px
2. Embed member data INTO the seal using steganography
3. Composite the embedded seal onto bottom-left of card image

Python 3.10+
Dependencies: Pillow, mutable_steganography
"""

import logging
from pathlib import Path
from typing import Dict, Optional
from PIL import Image
from mutable_steganography import MutableCardSteganography

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/seal_compositor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SealCompositor:
    """
    Handles RedSeal embedding and compositing onto member cards
    """
    
    SEAL_SIZE = (100, 100)  # Target seal size
    SEAL_POSITION = (10, None)  # (x, bottom_offset) - 10px from left, 10px from bottom
    
    def __init__(self, seal_path: Optional[str] = None):
        # Default to project-relative data/RedSeal.png if not provided
        if seal_path:
            self.seal_path = Path(seal_path)
        else:
            self.seal_path = Path(__file__).parent / 'data' / 'RedSeal.png'
        self.stego = MutableCardSteganography()
        
        # Ensure seal exists
        if not self.seal_path.exists():
            logger.warning(f"RedSeal not found at {seal_path}")
            # Create a default red seal if missing
            self._create_default_seal()
        
        logger.info(f"SealCompositor initialized with seal: {self.seal_path}")
    
    def _create_default_seal(self):
        """Create a default red seal if RedSeal.png is missing"""
        try:
            # Ensure data directory exists
            self.seal_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create a simple red circular seal
            seal_img = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
            pixels = seal_img.load()
            
            # Draw a red circle
            center_x, center_y = 50, 50
            radius = 45
            
            for y in range(100):
                for x in range(100):
                    dist = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                    if dist <= radius:
                        # Red with gradient
                        alpha = int(255 * (1 - dist / radius * 0.3))
                        pixels[x, y] = (220, 38, 38, alpha)
            
            seal_img.save(str(self.seal_path), 'PNG')
            logger.info(f"Created default RedSeal at {self.seal_path}")
            
        except Exception as e:
            logger.error(f"Error creating default seal: {e}", exc_info=True)
    
    def embed_and_composite(
        self,
        card_path: str,
        member_data: Dict,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Complete workflow: Embed data in seal, then composite onto card
        
        Args:
            card_path: Path to base card image (512x768)
            member_data: Complete member account data to embed
            output_path: Where to save final card (default: overwrites card_path)
        
        Returns:
            Path to final card with embedded seal, or None on failure
        """
        try:
            logger.info(f"Starting seal embedding and compositing for card: {card_path}")
            
            # Step 1: Create embedded seal
            embedded_seal_path = self._create_embedded_seal(member_data)
            if not embedded_seal_path:
                logger.error("Failed to create embedded seal")
                return None
            
            # Step 2: Composite seal onto card
            final_card_path = self._composite_seal_on_card(
                card_path,
                embedded_seal_path,
                output_path
            )
            
            if final_card_path:
                logger.info(f"Successfully created card with embedded seal: {final_card_path}")
            else:
                logger.error("Failed to composite seal onto card")
            
            return final_card_path
            
        except Exception as e:
            logger.error(f"Error in embed_and_composite: {e}", exc_info=True)
            return None
    
    def _create_embedded_seal(self, member_data: Dict) -> Optional[str]:
        """
        Step 1: Embed member data into RedSeal
        
        Returns:
            Path to temporary embedded seal image
        """
        try:
            # Load original seal
            seal_img = Image.open(str(self.seal_path))
            
            # Resize to 25x25 (LANCZOS for quality)
            seal_resized = seal_img.resize(self.SEAL_SIZE, Image.Resampling.LANCZOS)
            
            # Save temporary resized seal
            temp_seal_path = self.seal_path.parent / "Redseal.png"
            seal_resized.save(str(temp_seal_path), 'PNG')
            
            logger.debug(f"Resized seal to {self.SEAL_SIZE}")
            
            # Embed member data into the seal using steganography
            # Note: 25x25 = 625 pixels * 3 channels = 1875 bits ≈ 234 bytes capacity
            # We need to compress the data or use minimal fields
            
            # Create compact data for seal embedding
            compact_data = {
                "member_id": member_data.get('member_id'),
                "name": member_data.get('member_profile', {}).get('name'),
                "tier": member_data.get('subscription', {}).get('tier'),
                "valid": True,
                "seal_version": "1.0"
            }
            
            # Embed into seal
            embedded_seal_path = self.seal_path.parent / "Redseal_embedded.png"
            self.stego.embed_data(
                str(temp_seal_path),
                compact_data,
                str(embedded_seal_path),
                force_overwrite=True
            )
            
            logger.debug(f"Embedded data into seal: {embedded_seal_path}")
            
            return str(embedded_seal_path)
            
        except Exception as e:
            logger.error(f"Error creating embedded seal: {e}", exc_info=True)
            return None
    
    def _composite_seal_on_card(
        self,
        card_path: str,
        seal_path: str,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Step 2: Composite embedded seal onto bottom-left corner of card
        
        Args:
            card_path: Base card image (512x768)
            seal_path: Embedded seal image (25x25)
            output_path: Where to save (default: overwrites card_path)
        
        Returns:
            Path to final composited card
        """
        try:
            # Load card and seal
            card_img = Image.open(card_path).convert('RGBA')
            seal_img = Image.open(seal_path).convert('RGBA')
            
            card_width, card_height = card_img.size
            seal_width, seal_height = seal_img.size
            
            # Calculate position: bottom-left corner with 10px padding
            x_pos = self.SEAL_POSITION[0]  # 10px from left
            y_pos = card_height - seal_height - 10  # 10px from bottom
            
            logger.debug(f"Compositing seal at position ({x_pos}, {y_pos})")
            
            # Composite seal onto card (alpha blending)
            card_img.paste(seal_img, (x_pos, y_pos), seal_img)
            
            # Save final card
            if output_path is None:
                output_path = card_path
            
            # Convert back to RGB if needed (PNG supports RGBA)
            card_img.save(output_path, 'PNG')
            
            logger.info(f"Composited seal onto card: {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error compositing seal: {e}", exc_info=True)
            return None
    
    def extract_seal_data(self, card_path: str) -> Optional[Dict]:
        """
        Extract data from the seal on a card
        
        Args:
            card_path: Card image with embedded seal
        
        Returns:
            Extracted seal data or None if not found/invalid
        """
        try:
            # Load card
            card_img = Image.open(card_path).convert('RGBA')
            card_width, card_height = card_img.size
            
            # Extract seal region (bottom-left 25x25)
            x_pos = self.SEAL_POSITION[0]
            y_pos = card_height - self.SEAL_SIZE[1] - 10
            
            seal_region = card_img.crop((
                x_pos,
                y_pos,
                x_pos + self.SEAL_SIZE[0],
                y_pos + self.SEAL_SIZE[1]
            ))
            
            # Save temporary seal
            temp_seal_path = self.seal_path.parent / "Redseal_extracted.png"
            seal_region.save(str(temp_seal_path), 'PNG')
            
            # Extract data from seal
            seal_data = self.stego.extract_data(str(temp_seal_path))
            
            logger.info(f"Extracted seal data from card: {card_path}")
            
            return seal_data
            
        except Exception as e:
            logger.error(f"Error extracting seal data: {e}", exc_info=True)
            return None
    
    def validate_seal(self, card_path: str) -> bool:
        """
        Validate that a card has a valid embedded seal
        
        Args:
            card_path: Card image to validate
        
        Returns:
            True if seal is valid, False otherwise
        """
        try:
            seal_data = self.extract_seal_data(card_path)
            
            if not seal_data:
                logger.warning(f"No seal data found on card: {card_path}")
                return False
            
            # Check for required fields
            required_fields = ['member_id', 'name', 'tier', 'valid']
            for field in required_fields:
                if field not in seal_data:
                    logger.warning(f"Missing required field in seal: {field}")
                    return False
            
            # Check if marked as valid
            if not seal_data.get('valid', False):
                logger.warning(f"Seal marked as invalid")
                return False
            
            logger.info(f"Seal validated successfully for card: {card_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating seal: {e}", exc_info=True)
            return False


# Convenience functions
def quick_seal_and_embed(card_path: str, member_data: Dict, output_path: Optional[str] = None) -> Optional[str]:
    """Quick function to seal and embed a card"""
    compositor = SealCompositor()
    return compositor.embed_and_composite(card_path, member_data, output_path)


def validate_card_seal(card_path: str) -> bool:
    """Quick function to validate a card's seal"""
    compositor = SealCompositor()
    return compositor.validate_seal(card_path)


# Test
if __name__ == '__main__':
    print("RedSeal Compositor Test")
    print("=" * 50)
    
    compositor = SealCompositor()
    
    # Test data
    test_member_data = {
        "member_id": "m_test123",
        "member_profile": {
            "name": "Test User",
            "email": "test@example.com"
        },
        "subscription": {
            "tier": "Premium"
        }
    }
    
    # This would be tested with an actual card image
    print("✓ SealCompositor initialized")
    print(f"  Seal path: {compositor.seal_path}")
    print(f"  Seal size: {compositor.SEAL_SIZE}")
    print(f"  Ready for embedding")
