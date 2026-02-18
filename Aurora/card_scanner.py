"""
Aurora Archive - Card Scanner Module
Scans embedded card data, displays account details, and manages multi-user database

Supports multiple card formats:
- Aurora Archive member cards (member_schema.json format)
- AetherCards soul cards (SOUL_MANIFEST.json format)
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from mutable_steganography import MutableCardSteganography


class CardDataError(Exception):
    """Base exception for card data errors"""
    pass


class CardFormat:
    """Enum for supported card formats"""
    AURORA_MEMBER = "aurora_member"
    AETHER_SOUL = "aether_soul"
    UNKNOWN = "unknown"


class UserDatabase:
    """
    Manages multiple user accounts in a side database
    Stores all registered users and their associated cards
    """
    
    def __init__(self, db_path: str = "data/users_database.json"):
        """
        Initialize user database
        
        Args:
            db_path: Path to the JSON database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.users = self._load_database()
    
    def _load_database(self) -> Dict:
        """Load user database from file"""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load database: {e}")
                return {"users": [], "last_updated": None}
        return {"users": [], "last_updated": None}
    
    def _save_database(self):
        """Save user database to file"""
        try:
            self.users["last_updated"] = datetime.now().isoformat()
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving database: {e}")
    
    def add_user(self, user_data: Dict, card_format: str, card_image_path: str = "") -> str:
        """
        Add or update a user in the database
        
        Args:
            user_data: Complete user data from card
            card_format: Format type (aurora_member or aether_soul)
            card_image_path: Path to the card image file
            
        Returns:
            User ID
        """
        # Generate unique user ID based on card data
        user_id = self._generate_user_id(user_data, card_format)
        
        # Check if user already exists
        existing_user = self.get_user(user_id)
        
        if existing_user:
            # Update existing user
            for user in self.users["users"]:
                if user["user_id"] == user_id:
                    user["data"] = user_data
                    user["format"] = card_format
                    user["card_image_path"] = card_image_path
                    user["last_scan"] = datetime.now().isoformat()
                    user["scan_count"] = user.get("scan_count", 0) + 1
                    break
        else:
            # Add new user
            self.users["users"].append({
                "user_id": user_id,
                "data": user_data,
                "format": card_format,
                "card_image_path": card_image_path,
                "first_scan": datetime.now().isoformat(),
                "last_scan": datetime.now().isoformat(),
                "scan_count": 1
            })
        
        self._save_database()
        return user_id
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user data by ID"""
        for user in self.users["users"]:
            if user["user_id"] == user_id:
                return user
        return None
    
    def get_all_users(self) -> List[Dict]:
        """Get all registered users"""
        return self.users["users"]
    
    def remove_user(self, user_id: str) -> bool:
        """Remove a user from database"""
        initial_count = len(self.users["users"])
        self.users["users"] = [u for u in self.users["users"] if u["user_id"] != user_id]
        
        if len(self.users["users"]) < initial_count:
            self._save_database()
            return True
        return False
    
    def clear_database(self):
        """Clear all users (use with caution!)"""
        self.users = {"users": [], "last_updated": None}
        self._save_database()
    
    def _generate_user_id(self, user_data: Dict, card_format: str) -> str:
        """Generate unique user ID from card data"""
        if card_format == CardFormat.AURORA_MEMBER:
            # Use member_id if available, otherwise generate from name + email
            if "member_id" in user_data:
                return user_data["member_id"]
            
            # Generate from profile data
            profile = user_data.get("member_profile", {})
            id_string = f"{profile.get('name', '')}_{profile.get('email', '')}"
            
        elif card_format == CardFormat.AETHER_SOUL:
            # Use soul_name + exported_at as unique identifier
            soul_name = user_data.get("soul_name", "unknown")
            exported_at = user_data.get("exported_at", "")
            id_string = f"soul_{soul_name}_{exported_at}"
        
        else:
            # Fallback: hash entire data
            id_string = json.dumps(user_data, sort_keys=True)
        
        # Create hash for consistent ID
        return hashlib.md5(id_string.encode()).hexdigest()[:12]


class CardScanner:
    """
    Main card scanner class
    Reads embedded card data and identifies format
    """
    
    def __init__(self, database_path: str = "data/users_database.json"):
        """
        Initialize card scanner
        
        Args:
            database_path: Path to user database
        """
        self.stego = MutableCardSteganography()
        self.database = UserDatabase(database_path)
        self.current_user = None
        self.current_format = None
    
    def scan_card(self, card_image_path: str, register_user: bool = True) -> Tuple[Dict, str]:
        """
        Scan a card image and extract all data
        
        Args:
            card_image_path: Path to card image (with embedded data)
            register_user: If True, add user to database
            
        Returns:
            Tuple of (extracted_data, card_format)
            
        Raises:
            CorruptedDataError: If card data is corrupted
            FileNotFoundError: If card image doesn't exist
        """
        if not Path(card_image_path).exists():
            raise FileNotFoundError(f"Card image not found: {card_image_path}")
        
        # Extract embedded data
        try:
            raw_data = self.stego.extract_data(card_image_path)
        except (ValueError, json.JSONDecodeError) as e:
            raise CardDataError(f"Card does not contain valid embedded data: {e}")
        
        # Identify card format
        card_format = self._identify_format(raw_data)
        
        # Store current user
        self.current_user = raw_data
        self.current_format = card_format
        
        # Register user in database with card image path
        if register_user:
            user_id = self.database.add_user(raw_data, card_format, str(Path(card_image_path).absolute()))
            print(f"✓ User registered/updated: {user_id}")
        
        return (raw_data, card_format)
    
    def _identify_format(self, data: Dict) -> str:
        """
        Identify the card format from extracted data
        
        Args:
            data: Extracted card data
            
        Returns:
            Card format identifier
        """
        # Check for Aurora Archive member card markers (full schema)
        if "member_profile" in data and "subscription" in data:
            return CardFormat.AURORA_MEMBER
        
        # Check for Aurora Archive member card markers (simplified/legacy)
        if "member_id" in data and ("tier" in data or "subscription" in data):
            return CardFormat.AURORA_MEMBER
        
        # Check for basic Aurora card markers
        if "card_id" in data and data.get("card_id", "").startswith("aurora_"):
            return CardFormat.AURORA_MEMBER
        
        # Check for AetherCards soul markers
        if "soul_name" in data and ("species" in data or "archetype" in data):
            return CardFormat.AETHER_SOUL
        
        # Check for SOUL_MANIFEST format (external file reference)
        if "files" in data and "soul_data" in data.get("files", {}):
            return CardFormat.AETHER_SOUL
        
        return CardFormat.UNKNOWN
    
    def display_account_details(self, data: Dict = None, card_format: str = None) -> str:
        """
        Format account details for display
        
        Args:
            data: Card data (uses current_user if None)
            card_format: Card format (uses current_format if None)
            
        Returns:
            Formatted string for display
        """
        if data is None:
            data = self.current_user
        if card_format is None:
            card_format = self.current_format
        
        if data is None:
            return "No card data loaded. Please scan a card first."
        
        # Format based on card type
        if card_format == CardFormat.AURORA_MEMBER:
            return self._format_aurora_member(data)
        elif card_format == CardFormat.AETHER_SOUL:
            return self._format_aether_soul(data)
        else:
            return self._format_unknown(data)
    
    def _format_aurora_member(self, data: Dict) -> str:
        """Format Aurora Archive member card for display"""
        
        # Check if this is full schema or legacy/simplified schema
        if "member_profile" in data:
            # Full schema
            profile = data.get("member_profile", {})
            subscription = data.get("subscription", {})
            usage = data.get("usage_stats", {})
            preferences = data.get("preferences", {})
            name = profile.get('name', 'N/A')
            email = profile.get('email', 'N/A')
            tier = subscription.get('tier', 'N/A')
            member_id = data.get('member_id', 'N/A')
        else:
            # Legacy/simplified schema
            profile = data
            subscription = data.get("subscription", {})
            usage = {}
            preferences = {}
            name = data.get('name', 'N/A')
            email = data.get('email', 'N/A')
            tier = data.get('tier', 'N/A')
            member_id = data.get('member_id', 'N/A')
        
        output = []
        output.append("╔" + "═" * 58 + "╗")
        output.append("║" + " " * 15 + "AURORA ARCHIVE MEMBER CARD" + " " * 17 + "║")
        output.append("╚" + "═" * 58 + "╝")
        output.append("")
        
        # Member Profile
        output.append("👤 MEMBER PROFILE")
        output.append("─" * 60)
        output.append(f"  Name:           {name}")
        output.append(f"  Member ID:      {member_id}")
        output.append(f"  Email:          {email}")
        
        if "member_profile" in data:
            # Full schema fields
            output.append(f"  Location:       {profile.get('location', 'N/A')}")
            output.append(f"  Age:            {profile.get('age', 'N/A')}")
            output.append(f"  Gender:         {profile.get('gender', 'N/A')}")
            output.append(f"  Bio:            {profile.get('bio', 'N/A')}")
            output.append(f"  Interests:      {', '.join(profile.get('interests', []))}")
        
        output.append("")
        
        # Subscription
        output.append("💳 SUBSCRIPTION")
        output.append("─" * 60)
        output.append(f"  Tier:           {tier}")
        
        if subscription:
            output.append(f"  Status:         {subscription.get('status', 'N/A').upper()}")
            if "monthly_cost" in subscription:
                output.append(f"  Monthly Cost:   ${subscription.get('monthly_cost', 0):.2f}")
            if "next_billing_date" in subscription or "next_billing" in subscription:
                next_billing = subscription.get('next_billing_date') or subscription.get('next_billing')
                output.append(f"  Next Billing:   {next_billing}")
            if "auto_renew" in subscription:
                output.append(f"  Auto-Renew:     {'Yes' if subscription.get('auto_renew') else 'No'}")
        
        output.append("")
        
        # Usage Statistics (if available)
        if usage or "cards_generated" in data:
            output.append("📊 USAGE STATISTICS")
            output.append("─" * 60)
            cards_generated = usage.get('cards_generated') or data.get('cards_generated', 0)
            output.append(f"  Cards Generated: {cards_generated}")
            
            if "last_generation_date" in usage:
                output.append(f"  Last Generation: {usage.get('last_generation_date', 'Never')}")
            
            if "daily_generations_used" in usage:
                daily_used = usage.get('daily_generations_used', 0)
                daily_limit = usage.get('daily_generation_limit', -1)
                limit_str = "Unlimited" if daily_limit == -1 else str(daily_limit)
                output.append(f"  Daily Usage:     {daily_used} / {limit_str}")
            
            output.append("")
        
        # Preferences
        if preferences:
            output.append("⚙️  PREFERENCES")
            output.append("─" * 60)
            
            card_prefs = preferences.get('card_generation', {})
            if card_prefs:
                output.append(f"  Art Style:       {card_prefs.get('art_style', 'N/A')}")
                output.append(f"  Color Scheme:    {card_prefs.get('color_scheme', 'N/A')}")
                output.append(f"  Card Border:     {card_prefs.get('card_border', 'N/A')}")
            output.append("")
        
        # Rentals
        rentals = data.get("rentals", [])
        if rentals:
            output.append("📚 ACTIVE RENTALS")
            output.append("─" * 60)
            for rental in rentals:
                output.append(f"  📖 {rental.get('title', 'Unknown Book')}")
                output.append(f"     Book ID:      {rental.get('book_id', 'N/A')}")
                output.append(f"     Due Date:     {rental.get('due_date', 'N/A')}")
                output.append(f"     Daily Rate:   ${rental.get('daily_rate', 0):.2f}")
                output.append(f"     Total Cost:   ${rental.get('total_cost', 0):.2f}")
                if "days_remaining" in rental:
                    output.append(f"     Days Left:    {rental.get('days_remaining', 0)}")
                output.append("")
        
        # Security Info
        security = data.get("security", {})
        if security:
            output.append("🔒 SECURITY")
            output.append("─" * 60)
            output.append(f"  Hash Algorithm:  {security.get('hash_algorithm', 'N/A')}")
            output.append(f"  Last Verified:   {security.get('last_verified', 'Never')}")
            output.append(f"  Card Hash:       {security.get('steganographic_hash', 'N/A')[:20]}...")
            output.append("")
        
        # Card Collection
        cards = data.get("cards", [])
        if cards:
            output.append(f"🎴 CARD COLLECTION ({len(cards)} cards)")
            output.append("─" * 60)
            for i, card in enumerate(cards[:3], 1):  # Show first 3
                output.append(f"  {i}. {card.get('card_id', 'N/A')}")
                output.append(f"     Style:        {card.get('art_style', 'N/A')} | {card.get('color_scheme', 'N/A')}")
                output.append(f"     Generated:    {card.get('generation_date', 'N/A')}")
            if len(cards) > 3:
                output.append(f"     ... and {len(cards) - 3} more cards")
            output.append("")
        
        # Database pointer (legacy)
        if "database_pointer" in data:
            output.append("📍 DATABASE")
            output.append("─" * 60)
            output.append(f"  Pointer:         {data.get('database_pointer', 'N/A')}")
            output.append("")
        
        # Creation info (legacy)
        if "created" in data:
            output.append("📅 METADATA")
            output.append("─" * 60)
            output.append(f"  Created:         {data.get('created', 'N/A')}")
            output.append("")
        
        return "\n".join(output)
    
    def _format_aether_soul(self, data: Dict) -> str:
        """Format AetherCards soul card for display"""
        output = []
        output.append("╔" + "═" * 58 + "╗")
        output.append("║" + " " * 17 + "AETHERCARD SOUL DATA" + " " * 21 + "║")
        output.append("╚" + "═" * 58 + "╝")
        output.append("")
        
        # Basic Info
        output.append("✨ SOUL IDENTITY")
        output.append("─" * 60)
        output.append(f"  Soul Name:      {data.get('soul_name', data.get('name', 'N/A'))}")
        output.append(f"  Species:        {data.get('species', 'N/A')}")
        output.append(f"  Archetype:      {data.get('archetype', 'N/A')}")
        output.append(f"  Role:           {data.get('role', 'N/A')}")
        output.append(f"  Appears Age:    {data.get('appears_age', 'N/A')}")
        
        # Export info if available
        if "exported_at" in data:
            output.append(f"  Exported:       {data.get('exported_at', 'N/A')}")
        output.append("")
        
        # Appearance
        output.append("👁️  APPEARANCE")
        output.append("─" * 60)
        
        aesthetic = data.get("aesthetic", data)  # Try nested or root level
        
        output.append(f"  Color Palette:  {data.get('color_palette', 'N/A')}")
        output.append(f"  Hair:           {aesthetic.get('hair_color', 'N/A')} - {aesthetic.get('hair_style', 'N/A')}")
        output.append(f"  Hair Length:    {aesthetic.get('hair_length', 'N/A')}")
        output.append(f"  Eyes:           {aesthetic.get('eye_color', 'N/A')} ({aesthetic.get('eye_type', 'N/A')})")
        output.append(f"  Face:           {aesthetic.get('face_type', 'N/A')}")
        
        face_features = aesthetic.get('face_features', data.get('face_features', ''))
        if face_features:
            output.append(f"  Features:       {face_features}")
        output.append("")
        
        # Physical Stats
        body_type = data.get("body_type", data)
        if "height" in body_type or "height" in data:
            output.append("📏 PHYSICAL STATS")
            output.append("─" * 60)
            output.append(f"  Height:         {body_type.get('height', data.get('height', 'N/A'))} cm")
            output.append(f"  Weight:         {body_type.get('weight', data.get('weight', 'N/A'))} kg")
            output.append(f"  Body Fat:       {body_type.get('bodyfat', data.get('bodyfat', 'N/A'))}%")
            output.append(f"  Conditioning:   {body_type.get('conditioning', data.get('conditioning', 'N/A'))}")
            output.append("")
        
        # Attire
        if "clothing" in data:
            output.append("👔 ATTIRE")
            output.append("─" * 60)
            output.append(f"  Clothing:       {data.get('clothing', 'N/A')}")
            if data.get('accessories'):
                output.append(f"  Accessories:    {data.get('accessories', 'N/A')}")
            output.append("")
        
        # Background
        if data.get("backstory") or data.get("origin"):
            output.append("📜 BACKGROUND")
            output.append("─" * 60)
            if data.get("origin"):
                output.append(f"  Origin:         {data.get('origin', 'N/A')}")
            if data.get("backstory"):
                output.append(f"  Backstory:      {data.get('backstory', 'N/A')[:100]}...")
            if data.get("relationship"):
                output.append(f"  Relationship:   {data.get('relationship', 'N/A')}")
            output.append("")
        
        # Files (if SOUL_MANIFEST format)
        files = data.get("files", {})
        if files:
            output.append("📁 MANIFEST FILES")
            output.append("─" * 60)
            for file_type, file_path in files.items():
                output.append(f"  {file_type:15s} {file_path}")
            output.append("")
        
        return "\n".join(output)
    
    def _format_unknown(self, data: Dict) -> str:
        """Format unknown card format (generic JSON display)"""
        output = []
        output.append("╔" + "═" * 58 + "╗")
        output.append("║" + " " * 20 + "UNKNOWN CARD FORMAT" + " " * 19 + "║")
        output.append("╚" + "═" * 58 + "╝")
        output.append("")
        output.append("Raw JSON Data:")
        output.append("─" * 60)
        output.append(json.dumps(data, indent=2))
        return "\n".join(output)
    
    def switch_user(self, user_id: str) -> bool:
        """
        Switch to a different registered user
        
        Args:
            user_id: ID of user to switch to
            
        Returns:
            True if switch successful
        """
        user = self.database.get_user(user_id)
        if user:
            self.current_user = user["data"]
            self.current_format = user["format"]
            return True
        return False
    
    def clear_current_user(self):
        """Clear current user (logout)"""
        self.current_user = None
        self.current_format = None
    
    def list_all_users(self) -> str:
        """Get formatted list of all registered users"""
        users = self.database.get_all_users()
        
        if not users:
            return "No users registered in database."
        
        output = []
        output.append("╔" + "═" * 58 + "╗")
        output.append("║" + " " * 17 + "REGISTERED USERS" + " " * 25 + "║")
        output.append("╚" + "═" * 58 + "╝")
        output.append("")
        
        for i, user in enumerate(users, 1):
            user_data = user["data"]
            
            # Get display name based on format
            if user["format"] == CardFormat.AURORA_MEMBER:
                name = user_data.get("member_profile", {}).get("name", "Unknown")
                tier = user_data.get("subscription", {}).get("tier", "N/A")
                detail = f"Tier: {tier}"
            elif user["format"] == CardFormat.AETHER_SOUL:
                name = user_data.get("soul_name", user_data.get("name", "Unknown"))
                species = user_data.get("species", "N/A")
                detail = f"Species: {species}"
            else:
                name = "Unknown User"
                detail = "Unknown Format"
            
            output.append(f"{i}. {name}")
            output.append(f"   User ID:      {user['user_id']}")
            output.append(f"   Format:       {user['format']}")
            output.append(f"   {detail}")
            output.append(f"   Last Scan:    {user['last_scan']}")
            output.append(f"   Total Scans:  {user['scan_count']}")
            output.append("")
        
        return "\n".join(output)


# Convenience functions
def scan_and_display(card_image_path: str, register: bool = True) -> str:
    """
    Quick function to scan a card and display details
    
    Args:
        card_image_path: Path to card image
        register: Register user in database
        
    Returns:
        Formatted account details
    """
    scanner = CardScanner()
    data, card_format = scanner.scan_card(card_image_path, register)
    return scanner.display_account_details(data, card_format)


# Example usage
if __name__ == '__main__':
    print("Aurora Archive - Card Scanner Test")
    print("=" * 60)
    print()
    
    # Test with Aurora member card (project-relative test fixture)
    test_aurora_card = str(Path(__file__).parent.parent / 'data' / 'cards' / 'm_c4a05352_generic.png')
    
    scanner = CardScanner()
    
    try:
        print("📷 Scanning Aurora member card...")
        data, format_type = scanner.scan_card(test_aurora_card)
        print(f"✓ Card format detected: {format_type}")
        print()
        
        print(scanner.display_account_details())
        print()
        
        print("─" * 60)
        print("All registered users:")
        print("─" * 60)
        print(scanner.list_all_users())
        
    except FileNotFoundError:
        print("❌ Test card not found. Please provide a valid card image path.")
    except CardDataError as e:
        print(f"❌ Card data error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
