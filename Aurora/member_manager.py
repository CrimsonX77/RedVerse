"""
Aurora Archive - Member Registration Module
Complete member registration system with editable fields
Age-based tier assignment with Kids tier restrictions
"""

import json
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Dict, Optional, Tuple
from mutable_steganography import MutableCardSteganography


class MemberManager:
    """
    Manages member creation, editing, and card generation
    Handles complete member_schema structure with age-based tier restrictions
    """

    # Phase 2: 7-Tier Access System Configuration
    TIER_CONFIG = {
        1: {"name": "Wanderer",      "memory_depth": 0,   "cross_site": False, "custom_soul": False},
        2: {"name": "Initiate",      "memory_depth": 10,  "cross_site": False, "custom_soul": False},
        3: {"name": "Acolyte",       "memory_depth": 25,  "cross_site": False, "custom_soul": False},
        4: {"name": "Keeper",        "memory_depth": 50,  "cross_site": True,  "custom_soul": False},
        5: {"name": "Sentinel",      "memory_depth": 100, "cross_site": True,  "custom_soul": True},
        6: {"name": "Archon",        "memory_depth": 500, "cross_site": True,  "custom_soul": True},
        7: {"name": "Inner Sanctum", "memory_depth": -1,  "cross_site": True,  "custom_soul": True},
    }

    def __init__(self):
        self.stego = MutableCardSteganography()
    
    @staticmethod
    def calculate_age_from_birthdate(birthdate: str) -> int:
        """
        Calculate age from birthdate string
        
        Args:
            birthdate: ISO format date string (YYYY-MM-DD)
            
        Returns:
            Age in years
        """
        try:
            birth_date = datetime.fromisoformat(birthdate).date()
            today = date.today()
            age = today.year - birth_date.year
            # Adjust if birthday hasn't occurred this year yet
            if (today.month, today.day) < (birth_date.month, birth_date.day):
                age -= 1
            return age
        except (ValueError, AttributeError):
            return 0
    
    @staticmethod
    def calculate_18th_birthday(birthdate: str) -> Optional[str]:
        """
        Calculate the date when user turns 18
        
        Args:
            birthdate: ISO format date string (YYYY-MM-DD)
            
        Returns:
            ISO date string of 18th birthday, or None if invalid
        """
        try:
            birth_date = datetime.fromisoformat(birthdate).date()
            eighteenth = date(birth_date.year + 18, birth_date.month, birth_date.day)
            return eighteenth.isoformat()
        except (ValueError, AttributeError):
            return None
    
    @staticmethod
    def determine_tier_from_age(age: Optional[int], requested_tier: str = "Standard") -> Tuple[str, str]:
        """
        Determine appropriate tier based on age with automatic Kids tier lock
        
        Args:
            age: User's age in years (None if not provided)
            requested_tier: Tier requested by user
            
        Returns:
            Tuple of (assigned_tier, reason)
            
        Rules:
            - If age < 18: Force Kids tier (cannot be overridden)
            - If age >= 18: Allow any tier
            - If age unknown: Default to Standard tier (safe default)
        """
        if age is None:
            return (requested_tier, "Age not provided, using requested tier")
        
        if age < 18:
            return ("Kids", f"Automatic Kids tier assignment (age {age} < 18)")
        
        # Age 18+: Allow any tier
        return (requested_tier, f"Age {age} >= 18, tier assignment allowed")
    
    def check_tier_upgrade_eligibility(self, member_data: Dict) -> Optional[Dict]:
        """
        Check if a Kids tier member is now eligible for upgrade to Standard
        
        Args:
            member_data: Complete member schema
            
        Returns:
            Dict with upgrade info if eligible, None otherwise
        """
        profile = member_data.get("member_profile", {})
        subscription = member_data.get("subscription", {})
        
        current_tier = subscription.get("tier", "Standard")
        birthdate = profile.get("birthdate")
        
        # Only check Kids tier members with birthdate
        if current_tier != "Kids" or not birthdate:
            return None
        
        age = self.calculate_age_from_birthdate(birthdate)
        
        if age >= 18:
            return {
                "eligible": True,
                "current_tier": "Kids",
                "new_tier": "Standard",
                "age": age,
                "message": f"🎉 Congratulations! You've turned {age} and are now eligible to upgrade from Kids to Standard tier!"
            }
        
        days_until_18 = (datetime.fromisoformat(self.calculate_18th_birthday(birthdate)).date() - date.today()).days
        
        return {
            "eligible": False,
            "current_tier": "Kids",
            "age": age,
            "days_until_eligible": days_until_18,
            "message": f"Kids tier will automatically upgrade to Standard in {days_until_18} days (when you turn 18)"
        }
        
    def generate_member_id(self, email: str) -> str:
        """Generate unique member ID from email"""
        hash_obj = hashlib.md5(email.lower().encode())
        return f"m_{hash_obj.hexdigest()[:8]}"
    
    def generate_card_id(self, member_id: str, version: int = 0) -> str:
        """Generate card ID"""
        return f"aurora_{member_id}_{version:03d}"
    
    def create_new_member(
        self,
        # Profile fields
        name: str,
        email: str,
        phone: str = "",
        gender: str = "Prefer not to say",
        age: Optional[int] = None,
        birthdate: Optional[str] = None,  # ISO format YYYY-MM-DD
        bio: str = "",
        location: str = "",
        interests: list = None,
        
        # Address
        street: str = "",
        city: str = "",
        state: str = "",
        zip_code: str = "",
        country: str = "",
        
        # Subscription
        tier: str = "Standard",
        billing_cycle: str = "monthly",
        auto_renew: bool = True,
        
        # Payment (optional - can be added later)
        payment_type: str = "",
        payment_last_four: str = "",
        payment_expiry: str = "",
        
        # Preferences
        art_style: str = "fantasy",
        color_scheme: str = "azure_silver",
        card_border: str = "tribal_arcane",
        email_notifications: bool = True,
        sms_notifications: bool = False,
        push_notifications: bool = True,
        reading_genres: list = None,
        reading_language: str = "en",
        font_size: str = "medium",
        theme: str = "dark",
        
        # Additional fields
        profile_picture: str = "",
        card_art: str = ""
    ) -> Dict:
        """
        Create complete member schema from provided information
        
        Args:
            Profile, address, subscription, payment, and preference fields
            birthdate: Optional ISO date string (YYYY-MM-DD) for age calculation
            
        Returns:
            Complete member_schema dictionary with age-appropriate tier assignment
            
        Note:
            - If birthdate provided: age calculated automatically
            - If age < 18: Tier forced to "Kids" regardless of requested tier
            - Kids tier members auto-upgrade to Standard on 18th birthday
        """
        
        # Calculate age from birthdate if provided
        calculated_age = age
        if birthdate:
            calculated_age = self.calculate_age_from_birthdate(birthdate)
        
        # Determine appropriate tier based on age (enforces Kids tier for under 18)
        assigned_tier, tier_reason = self.determine_tier_from_age(calculated_age, tier)
        
        # Generate IDs
        member_id = self.generate_member_id(email)
        card_id = self.generate_card_id(member_id)

        # Phase 2: Generate thread_id for per-user JSONL memory
        thread_id = str(uuid.uuid4())

        # Phase 2: Assign access tier (default Tier 1 - Wanderer)
        access_tier = 1
        tier_name = self.TIER_CONFIG[access_tier]["name"]

        # Timestamps
        now = datetime.utcnow()
        now_iso = now.isoformat() + "Z"
        
        # Subscription costs
        tier_costs = {
            "Kids": 5.00,
            "Standard": 10.00,
            "Premium": 15.00
        }
        monthly_cost = tier_costs.get(assigned_tier, 10.00)
        
        # Next billing date (1 month from now)
        next_billing = (now + timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Calculate 18th birthday for Kids tier auto-upgrade
        upgrade_date = None
        if assigned_tier == "Kids" and birthdate:
            upgrade_date = self.calculate_18th_birthday(birthdate)
        
        # Steganographic hash
        steg_hash = hashlib.sha256(f"{member_id}{email}{now_iso}".encode()).hexdigest()[:40]
        
        # Build complete member schema
        member_data = {
            "card_id": card_id,
            "member_id": member_id,

            # Phase 2: Per-User Memory & Access Control
            "thread_id": thread_id,
            "access_tier": access_tier,
            "tier_name": tier_name,
            "seal_status": "unsigned",
            "seal_verification_layer": None,
            "oracle_context": {},
            "edrive_context": {},

            "member_profile": {
                "name": name,
                "email": email,
                "phone": phone,
                "gender": gender,
                "age": calculated_age,  # Use calculated age
                "birthdate": birthdate,  # Store birthdate for age verification
                "bio": bio,
                "location": location,
                "interests": interests or [],
                "membership_tier": assigned_tier,  # Use age-appropriate tier
                "profile_picture": profile_picture,
                "card_art": card_art,
                "address": {
                    "street": street,
                    "city": city,
                    "state": state,
                    "zip": zip_code,
                    "country": country
                }
            },
            
            "subscription": {
                "tier": assigned_tier,  # Use age-appropriate tier
                "monthly_cost": monthly_cost,
                "billing_cycle": billing_cycle,
                "next_billing_date": next_billing,
                "status": "active",
                "auto_renew": auto_renew,
                "tier_assignment_reason": tier_reason,  # Document why this tier was assigned
                "auto_upgrade_date": upgrade_date  # Date when Kids tier auto-upgrades to Standard
            },
            
            "payment_method": {
                "type": payment_type or "not_provided",
                "token": "",  # Placeholder - should be encrypted vault reference
                "expiry": payment_expiry,
                "last_four": payment_last_four,
                "billing_address": {
                    "street": street,
                    "city": city,
                    "state": state,
                    "zip": zip_code
                }
            },
            
            "transaction_history": [],
            
            "rentals": [],
            
            "usage_stats": {
                "cards_generated": 0,
                "last_generation_date": None,
                "daily_generations_used": 0,
                "daily_generation_limit": -1 if tier == "Premium" else 10 if tier == "Standard" else 3
            },
            
            "preferences": {
                "card_generation": {
                    "art_style": art_style,
                    "color_scheme": color_scheme,
                    "card_border": card_border
                },
                "notification_settings": {
                    "email_notifications": email_notifications,
                    "sms_notifications": sms_notifications,
                    "push_notifications": push_notifications
                },
                "reading_preferences": {
                    "genres": reading_genres or ["fantasy", "sci-fi"],
                    "language": reading_language,
                    "font_size": font_size,
                    "theme": theme
                }
            },
            
            "security": {
                "steganographic_hash": steg_hash,
                "hash_algorithm": "SHA-256",
                "last_verified": now_iso
            },
            
            "cards": [],
            
            "reading_history": {
                "total_books_read": 0,
                "last_read_date": None,
                "favorite_genres": reading_genres or []
            },
            
            "pages_read": {
                "total_pages": 0,
                "average_pages_per_book": 0,
                "longest_book_read": {
                    "title": None,
                    "pages": 0,
                    "read_date": None
                }
            },
            
            "achievements": {
                "badges_earned": [],
                "total_achievements": 0,
                "next_achievement_goal": "Generate your first card"
            },
            
            "audit_trail": [
                {
                    "action": "account_created",
                    "timestamp": now_iso,
                    "details": f"New {tier} member account created"
                }
            ],
            
            "metadata": {
                "created_at": now_iso,
                "updated_at": now_iso,
                "version": "2.0.0",
                "schema_type": "aurora_member_full"
            }
        }
        
        return member_data
    
    def update_member(
        self,
        existing_data: Dict,
        updates: Dict,
        audit_message: str = "Member data updated"
    ) -> Dict:
        """
        Update existing member data with new values
        
        Args:
            existing_data: Current member data
            updates: Dictionary of fields to update (dot-notation supported)
            audit_message: Message for audit trail
            
        Returns:
            Updated member data
        """
        # Deep copy to avoid mutation
        import copy
        updated_data = copy.deepcopy(existing_data)
        
        # Apply updates (supports nested keys with dot-notation)
        for key, value in updates.items():
            keys = key.split('.')
            target = updated_data
            
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            
            target[keys[-1]] = value
        
        # Update metadata
        now_iso = datetime.utcnow().isoformat() + "Z"
        updated_data['metadata']['updated_at'] = now_iso
        
        # Add to audit trail
        if 'audit_trail' not in updated_data:
            updated_data['audit_trail'] = []
        
        updated_data['audit_trail'].append({
            "action": "member_updated",
            "timestamp": now_iso,
            "details": audit_message,
            "fields_changed": list(updates.keys())
        })
        
        return updated_data
    
    def create_member_card(
        self,
        member_data: Dict,
        template_image: str,
        output_path: str
    ) -> str:
        """
        Embed member data into card image using steganography
        
        Args:
            member_data: Complete member schema
            template_image: Base card image to use
            output_path: Where to save the member card
            
        Returns:
            Path to created card
        """
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Embed data
        result_path = self.stego.embed_data(
            template_image,
            member_data,
            output_path,
            force_overwrite=True
        )
        
        return result_path
    
    def add_rental(
        self,
        member_data: Dict,
        book_id: str,
        title: str,
        daily_rate: float = 1.00,
        rental_days: int = 14
    ) -> Dict:
        """Add a new rental to member"""
        now = datetime.utcnow()
        due_date = now + timedelta(days=rental_days)
        
        rental = {
            "book_id": book_id,
            "title": title,
            "rental_start": now.strftime("%Y-%m-%d"),
            "due_date": due_date.strftime("%Y-%m-%d"),
            "daily_rate": daily_rate,
            "total_cost": daily_rate * rental_days,
            "status": "active",
            "renewals": 0,
            "max_renewals": 2,
            "days_remaining": rental_days
        }
        
        if 'rentals' not in member_data:
            member_data['rentals'] = []
        
        member_data['rentals'].append(rental)
        
        # Update audit trail
        now_iso = now.isoformat() + "Z"
        member_data['audit_trail'].append({
            "action": "book_rented",
            "timestamp": now_iso,
            "details": f"Rented '{title}'",
            "book_id": book_id,
            "total_cost": rental['total_cost']
        })
        
        member_data['metadata']['updated_at'] = now_iso
        
        return member_data
    
    def add_transaction(
        self,
        member_data: Dict,
        amount: float,
        transaction_type: str,
        description: str
    ) -> Dict:
        """Add transaction to member history"""
        now = datetime.utcnow()
        
        transaction = {
            "transaction_id": f"rcpt_aurora_{hashlib.md5(str(now.timestamp()).encode()).hexdigest()[:10]}",
            "date": now.strftime("%Y-%m-%d"),
            "amount": amount,
            "type": transaction_type,
            "status": "completed",
            "description": description
        }
        
        if 'transaction_history' not in member_data:
            member_data['transaction_history'] = []
        
        member_data['transaction_history'].append(transaction)
        
        # Update audit trail
        now_iso = now.isoformat() + "Z"
        member_data['audit_trail'].append({
            "action": transaction_type,
            "timestamp": now_iso,
            "details": description,
            "amount": amount
        })
        
        member_data['metadata']['updated_at'] = now_iso
        
        return member_data
    
    def increment_card_generation(self, member_data: Dict) -> Dict:
        """Increment card generation count"""
        now_iso = datetime.utcnow().isoformat() + "Z"
        
        if 'usage_stats' not in member_data:
            member_data['usage_stats'] = {}
        
        member_data['usage_stats']['cards_generated'] = member_data['usage_stats'].get('cards_generated', 0) + 1
        member_data['usage_stats']['last_generation_date'] = now_iso
        member_data['usage_stats']['daily_generations_used'] = member_data['usage_stats'].get('daily_generations_used', 0) + 1
        
        member_data['metadata']['updated_at'] = now_iso
        
        return member_data


# Example usage
if __name__ == '__main__':
    print("=" * 60)
    print("Member Manager Test")
    print("=" * 60)
    
    manager = MemberManager()
    
    # Create new member
    print("\n1. Creating new member...")
    member = manager.create_new_member(
        name="Alex Thompson",
        email="alex.thompson@example.com",
        phone="+1234567890",
        gender="Non-binary",
        age=25,
        bio="Loves fantasy novels and card games",
        location="Portland, OR",
        interests=["reading", "gaming", "art"],
        street="456 Oak Street",
        city="Portland",
        state="OR",
        zip_code="97201",
        country="USA",
        tier="Premium",
        art_style="fantasy",
        color_scheme="emerald_gold"
    )
    
    print(f"✓ Member created: {member['member_id']}")
    print(f"  Name: {member['member_profile']['name']}")
    print(f"  Email: {member['member_profile']['email']}")
    print(f"  Tier: {member['subscription']['tier']}")
    print(f"  Monthly cost: ${member['subscription']['monthly_cost']}")
    
    # Add rental
    print("\n2. Adding rental...")
    member = manager.add_rental(
        member,
        book_id="aurora_book_123",
        title="The Dragon's Quest",
        daily_rate=1.50,
        rental_days=14
    )
    print(f"✓ Rental added: {member['rentals'][0]['title']}")
    
    # Add transaction
    print("\n3. Adding transaction...")
    member = manager.add_transaction(
        member,
        amount=15.00,
        transaction_type="subscription_renewal",
        description="Premium tier monthly renewal"
    )
    print(f"✓ Transaction added: ${member['transaction_history'][0]['amount']}")
    
    # Show complete structure
    print("\n4. Member structure:")
    print(f"  Top-level fields: {len(member)}")
    print(f"  Audit trail entries: {len(member['audit_trail'])}")
    print(f"  Rentals: {len(member['rentals'])}")
    print(f"  Transactions: {len(member['transaction_history'])}")
    
    print("\n✓ Member Manager test complete!")
