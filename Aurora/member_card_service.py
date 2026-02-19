"""
Member Card Service - Integrates seal embedding with member account creation

Workflow:
1. New member created from Google OAuth
2. Generate/access member card template
3. Embed crs.png seal with member data
4. Composite seal onto card (bottom-left)
5. Save final card to Assets/member_cards/
6. Update member database with card_path

Python 3.10+
Dependencies: Pillow, seal_compositor, database_manager
"""

import logging
from pathlib import Path
from typing import Optional, Dict
from PIL import Image
from datetime import datetime
from seal_compositor import SealCompositor

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/member_card_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MemberCardService:
    """
    Handles member card generation and seal embedding for new accounts
    """

    def __init__(self):
        # Paths
        self.project_root = Path(__file__).parent.parent
        self.seal_path = Path(__file__).parent / 'data' / 'crs.png'
        self.member_cards_dir = self.project_root / 'Assets' / 'member_cards'
        self.card_template_path = Path(__file__).parent / 'data' / 'card_template.png'

        # Create directories if needed
        self.member_cards_dir.mkdir(parents=True, exist_ok=True)

        # Initialize seal compositor
        self.seal_compositor = SealCompositor(str(self.seal_path))

        if not self.seal_path.exists():
            logger.warning(f"Seal (crs.png) not found at {self.seal_path}")

        logger.info("MemberCardService initialized")

    def generate_member_card(self, member_data: Dict) -> Optional[str]:
        """
        Complete workflow: Create card for new member with embedded seal

        Args:
            member_data: Complete member data from database
                {
                    'member_id': 'uuid',
                    'display_name': 'User Name',
                    'email': 'user@example.com',
                    'access_tier': 1,
                    'tier_name': 'Wanderer',
                    'thread_id': 'uuid',
                    'is_admin': False,
                    'created_at': '2026-02-19T...'
                }

        Returns:
            Path to final card with embedded seal, or None on failure
        """
        try:
            member_id = member_data.get('member_id')
            logger.info(f"Starting member card generation for {member_id}")

            # Step 1: Get or create base card
            card_path = self._get_base_card(member_id, member_data)
            if not card_path:
                logger.error("Failed to get base card")
                return None

            # Step 2: Embed seal with member data
            logger.debug(f"Compositing seal onto card")
            final_card_path = self.seal_compositor.embed_and_composite(
                card_path,
                member_data,
                output_path=None  # Overwrites card_path
            )

            if not final_card_path:
                logger.error("Failed to composite seal")
                return None

            logger.info(f"Successfully created member card: {final_card_path}")
            return final_card_path

        except Exception as e:
            logger.error(f"Error generating member card: {e}", exc_info=True)
            return None

    def _get_base_card(self, member_id: str, member_data: Dict) -> Optional[str]:
        """
        Step 1: Get or create a base card for the member

        Uses template or creates simple colored card with member info text

        Returns:
            Path to base card image
        """
        try:
            # Generate card filename
            card_filename = f"{member_id}_card.png"
            card_path = self.member_cards_dir / card_filename

            # If template exists, copy it
            if self.card_template_path.exists():
                logger.debug(f"Using card template: {self.card_template_path}")
                import shutil
                shutil.copy(str(self.card_template_path), str(card_path))
                logger.debug(f"Copied template to {card_path}")
                return str(card_path)

            # Otherwise create a simple card with member info
            logger.debug("Creating default member card")
            card_img = self._create_default_card(member_data)

            if card_img:
                card_img.save(str(card_path), 'PNG')
                logger.info(f"Created default card: {card_path}")
                return str(card_path)

            logger.error("Failed to create default card")
            return None

        except Exception as e:
            logger.error(f"Error getting base card: {e}", exc_info=True)
            return None

    def _create_default_card(self, member_data: Dict) -> Optional[Image.Image]:
        """
        Create a simple default card with member information

        Card format: 512x768px (standard trading card size)
        Layout:
          - Header area: Member name
          - Middle area: Tier and email
          - Footer area: Created date
          - Bottom-left: Seal will be composited here

        Returns:
            PIL Image object or None
        """
        try:
            from PIL import ImageDraw, ImageFont

            # Create card
            width, height = 512, 768
            card = Image.new('RGB', (width, height), color=(20, 20, 20))  # Dark background
            draw = ImageDraw.Draw(card)

            # Try to use nice fonts, fall back to default
            try:
                title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
                text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
                small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
            except:
                title_font = ImageFont.load_default()
                text_font = ImageFont.load_default()
                small_font = ImageFont.load_default()

            # Colors
            gold = (212, 168, 70)
            crimson = (196, 18, 48)
            white = (230, 224, 216)
            gray = (155, 142, 130)

            # Draw decorative border
            draw.rectangle([(5, 5), (width-5, height-5)], outline=crimson, width=2)
            draw.line([(10, 60), (width-10, 60)], fill=gold, width=1)

            # Member name (header)
            name = member_data.get('display_name', 'Unknown')
            draw.text((40, 30), name, fill=gold, font=title_font)

            # Tier and info
            tier_name = member_data.get('tier_name', 'Wanderer')
            tier_num = member_data.get('access_tier', 1)
            draw.text((40, 100), f"Tier {tier_num}: {tier_name}", fill=crimson, font=text_font)

            # Email
            email = member_data.get('email', '')
            draw.text((40, 140), email, fill=gray, font=text_font)

            # Member ID (truncated for display)
            member_id = member_data.get('member_id', '')
            member_id_short = member_id[:16] + "..." if len(member_id) > 16 else member_id
            draw.text((40, 180), f"ID: {member_id_short}", fill=gray, font=small_font)

            # Thread ID
            thread_id = member_data.get('thread_id', '')
            thread_id_short = thread_id[:16] + "..." if len(thread_id) > 16 else thread_id
            draw.text((40, 200), f"Thread: {thread_id_short}", fill=gray, font=small_font)

            # Authentication method
            auth_method = member_data.get('auth_method', 'google')
            draw.text((40, 240), f"Auth: {auth_method}", fill=white, font=small_font)

            # Created at
            created_at = member_data.get('created_at', '')
            if created_at:
                # Parse and format date
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at)
                    date_str = dt.strftime('%Y-%m-%d')
                except:
                    date_str = created_at[:10]
            else:
                date_str = datetime.now().strftime('%Y-%m-%d')

            draw.text((40, height - 60), f"Created: {date_str}", fill=gray, font=small_font)
            draw.text((40, height - 35), "RedVerse Member Card", fill=gold, font=small_font)

            logger.debug("Created default card image")
            return card

        except Exception as e:
            logger.error(f"Error creating default card: {e}", exc_info=True)
            return None

    def update_member_in_database(self, member_id: str, card_path: str, db) -> bool:
        """
        Update member database with card path

        Args:
            member_id: Member ID
            card_path: Path to generated card
            db: DatabaseManager instance

        Returns:
            True if successful
        """
        try:
            success = db.update_member(member_id, {
                'card_data': {
                    'current_card_path': card_path,
                    'last_updated': datetime.now().isoformat(),
                    'valid': True
                }
            })

            if success:
                logger.info(f"Updated member {member_id} with card path: {card_path}")
            else:
                logger.error(f"Failed to update member {member_id} in database")

            return success

        except Exception as e:
            logger.error(f"Error updating member in database: {e}", exc_info=True)
            return False


def create_member_card_for_account(member_data: Dict, db) -> Optional[str]:
    """
    Convenience function: Called when new member is created from Google OAuth

    Workflow:
    1. Generate card with embedded seal
    2. Update member database
    3. Return card path

    Args:
        member_data: Member data dict
        db: DatabaseManager instance

    Returns:
        Path to generated card or None
    """
    try:
        service = MemberCardService()

        # Generate card
        card_path = service.generate_member_card(member_data)
        if not card_path:
            logger.error("Failed to generate card")
            return None

        # Update database
        member_id = member_data.get('member_id')
        success = service.update_member_in_database(member_id, card_path, db)

        if success:
            return card_path
        else:
            logger.warning(f"Card generated but database update failed: {card_path}")
            return card_path  # Still return the path even if DB update failed

    except Exception as e:
        logger.error(f"Error in create_member_card_for_account: {e}", exc_info=True)
        return None
