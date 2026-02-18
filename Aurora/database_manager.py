"""
Aurora Archive - Database Manager
Handles member data storage, books inventory, and transaction logging

Python 3.10+
Dependencies: aiofiles
"""

import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import hashlib
import math
import os
from dotenv import load_dotenv

# Setup logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/database_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages all database operations for Aurora Archive
    - Member data (JSON + JSONL redundancy)
    - Books inventory
    - Transaction history
    - Card archiving
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Load environment variables
        load_dotenv()

        # Parse admin emails from environment
        admin_emails_str = os.getenv('ADMIN_EMAILS', '')
        self.admin_emails = set(
            email.strip().lower()
            for email in admin_emails_str.split(',')
            if email.strip()
        )

        if self.admin_emails:
            logger.info(f"Admin emails configured: {len(self.admin_emails)} admins")
        else:
            logger.warning("No admin emails configured in ADMIN_EMAILS environment variable")

        # Database paths
        self.members_db = self.data_dir / "members_database.json"
        self.members_jsonl = self.data_dir / "members_database.jsonl"
        self.books_db = self.data_dir / "books_inventory.json"
        self.transactions_db = self.data_dir / "transactions.jsonl"
        
        # Card storage paths
        self.cards_dir = Path(__file__).parent.parent / "Assets" / "member_cards"
        self.cards_dir.mkdir(parents=True, exist_ok=True)
        self.archived_cards_dir = self.data_dir / "archived_cards"
        self.archived_cards_dir.mkdir(exist_ok=True)
        
        # In-memory cache
        self.members = {}
        self.books = {}
        
        # Initialize databases
        self._initialize_databases()
        
        logger.info(f"DatabaseManager initialized: {self.data_dir}")
    
    def _initialize_databases(self):
        """Initialize database files if they don't exist"""
        # Members database
        if not self.members_db.exists():
            self._save_members_db({
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "version": "1.0",
                    "total_members": 0
                },
                "members": {}
            })
            logger.info("Created members_database.json")
        
        # Books inventory
        if not self.books_db.exists():
            self._save_books_db({
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "version": "1.0",
                    "total_books": 0
                },
                "books": {}
            })
            logger.info("Created books_inventory.json")
        
        # Load into memory
        self._load_databases()
    
    def _load_databases(self):
        """Load databases into memory"""
        try:
            # Load members
            with open(self.members_db, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.members = data.get('members', {})
                logger.debug(f"Loaded {len(self.members)} members")
            
            # Load books
            with open(self.books_db, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.books = data.get('books', {})
                logger.debug(f"Loaded {len(self.books)} books")
                
        except Exception as e:
            logger.error(f"Error loading databases: {e}", exc_info=True)
    
    def _save_members_db(self, data: Dict):
        """Save members database (JSON + JSONL redundancy)"""
        try:
            # Save JSON
            with open(self.members_db, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Save JSONL redundancy (one member per line)
            with open(self.members_jsonl, 'w', encoding='utf-8') as f:
                for member_id, member_data in data.get('members', {}).items():
                    entry = {"member_id": member_id, **member_data}
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            
            logger.debug("Saved members database (JSON + JSONL)")
        except Exception as e:
            logger.error(f"Error saving members database: {e}", exc_info=True)
    
    def _save_books_db(self, data: Dict):
        """Save books database"""
        try:
            with open(self.books_db, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug("Saved books database")
        except Exception as e:
            logger.error(f"Error saving books database: {e}", exc_info=True)
    
    def _log_transaction(self, transaction: Dict):
        """Append transaction to JSONL log"""
        try:
            with open(self.transactions_db, 'a', encoding='utf-8') as f:
                f.write(json.dumps(transaction, ensure_ascii=False) + '\n')
            logger.debug(f"Logged transaction: {transaction.get('type')}")
        except Exception as e:
            logger.error(f"Error logging transaction: {e}", exc_info=True)
    
    # ============================================
    # MEMBER OPERATIONS
    # ============================================
    
    def add_member(self, member_data: Dict) -> bool:
        """Add new member to database"""
        try:
            member_id = member_data.get('member_id')
            if not member_id:
                logger.error("Member ID missing in member_data")
                return False
            
            # Add to memory
            self.members[member_id] = member_data
            
            # Save to disk
            self._save_members_db({
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "version": "1.0",
                    "total_members": len(self.members),
                    "last_updated": datetime.now().isoformat()
                },
                "members": self.members
            })
            
            # Log transaction
            self._log_transaction({
                "type": "member_added",
                "member_id": member_id,
                "timestamp": datetime.now().isoformat(),
                "name": member_data.get('member_profile', {}).get('name', 'Unknown')
            })
            
            logger.info(f"Added member: {member_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding member: {e}", exc_info=True)
            return False
    
    def update_member(self, member_id: str, updates: Dict) -> bool:
        """Update existing member"""
        try:
            if member_id not in self.members:
                logger.error(f"Member not found: {member_id}")
                return False
            
            # Deep update
            self._deep_update(self.members[member_id], updates)
            
            # Update timestamp
            if 'audit_trail' in self.members[member_id]:
                self.members[member_id]['audit_trail'].append({
                    "action": "data_updated",
                    "timestamp": datetime.now().isoformat(),
                    "changes": list(updates.keys())
                })
            
            # Save to disk
            self._save_members_db({
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "version": "1.0",
                    "total_members": len(self.members),
                    "last_updated": datetime.now().isoformat()
                },
                "members": self.members
            })
            
            logger.info(f"Updated member: {member_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating member: {e}", exc_info=True)
            return False
    
    def get_member(self, member_id: str) -> Optional[Dict]:
        """Get member data"""
        return self.members.get(member_id)

    def get_member_by_email(self, email: str) -> Optional[Dict]:
        """Get member by email address - for Google auth"""
        email_lower = email.lower().strip()
        for member in self.members.values():
            member_email = member.get('email', '').lower().strip()
            if member_email == email_lower:
                return member
        return None

    def _is_admin_email(self, email: str) -> bool:
        """
        Check if email address is in admin whitelist

        Args:
            email: Email address to check

        Returns:
            True if email is in ADMIN_EMAILS list, False otherwise
        """
        email_lower = email.lower().strip()
        return email_lower in self.admin_emails

    def create_new_member_from_google(self, email: str, name: str, google_sub: str) -> Optional[Dict]:
        """Create new member from Google OAuth login"""
        try:
            import uuid

            member_id = str(uuid.uuid4())
            thread_id = str(uuid.uuid4())

            # Determine if user is admin based on email whitelist
            is_admin = self._is_admin_email(email)
            admin_status = "PROMOTED TO ADMIN" if is_admin else "regular user"

            member_data = {
                'id': member_id,
                'member_id': member_id,
                'email': email.lower().strip(),
                'display_name': name,
                'google_sub': google_sub,
                'access_tier': 1,  # Default to Tier 1 (Wanderer)
                'tier_name': 'Wanderer',
                'thread_id': thread_id,
                'is_admin': is_admin,  # ← Determined by email whitelist
                'auth_method': 'google',
                'created_at': datetime.now().isoformat(),
                'member_profile': {
                    'name': name,
                    'email': email.lower().strip()
                },
                'memory_sharing_mode': 'isolated',
                'trusted_users': [],
                'card_data': {
                    'current_card_path': None,
                    'last_updated': None,
                    'valid': False
                },
                'rentals': [],
                'audit_trail': [
                    {
                        'action': 'account_created_via_google',
                        'timestamp': datetime.now().isoformat(),
                        'details': f'Created via Google OAuth: {email} ({admin_status})'
                    }
                ]
            }

            # Add to memory
            self.members[member_id] = member_data

            # Save to disk
            self._save_members_db({
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "version": "1.0",
                    "total_members": len(self.members),
                    "last_updated": datetime.now().isoformat()
                },
                "members": self.members
            })

            # Log transaction
            self._log_transaction({
                "type": "member_created_google",
                "member_id": member_id,
                "email": email,
                "timestamp": datetime.now().isoformat(),
                "google_sub": google_sub,
                "is_admin": is_admin
            })

            logger.info(f"Created new member from Google OAuth: {email} (ID: {member_id}, Thread: {thread_id}, {admin_status})")
            return member_data

        except Exception as e:
            logger.error(f"Error creating member from Google OAuth: {e}", exc_info=True)
            return None

    def set_memory_sharing_mode(self, member_id: str, mode: str, pooled_tier: Optional[int] = None) -> bool:
        """
        Set memory sharing mode for member (isolated, trusted, or pooled)

        Args:
            member_id: Member ID
            mode: "isolated" | "trusted" | "pooled"
            pooled_tier: Tier number (4-7) if mode is "pooled"

        Returns:
            True if successful
        """
        try:
            if member_id not in self.members:
                logger.error(f"Member not found: {member_id}")
                return False

            if mode not in ["isolated", "trusted", "pooled"]:
                logger.error(f"Invalid sharing mode: {mode}")
                return False

            # Only Tier 4+ can use sharing
            member = self.members[member_id]
            if member.get('access_tier', 1) < 4 and mode != "isolated":
                logger.warning(f"Member {member_id} tier < 4, cannot use {mode} sharing")
                return False

            self.members[member_id]['memory_sharing_mode'] = mode
            if mode == "pooled":
                self.members[member_id]['pooled_tier'] = pooled_tier or member.get('access_tier')

            self.update_member(member_id, {'memory_sharing_mode': mode, 'pooled_tier': pooled_tier})
            logger.info(f"Set {mode} sharing mode for member {member_id}")
            return True

        except Exception as e:
            logger.error(f"Error setting sharing mode: {e}", exc_info=True)
            return False

    def add_trusted_user(self, member_id: str, trusted_member_id: str) -> bool:
        """
        Add trusted user (bidirectional)

        Args:
            member_id: The user adding a trusted connection
            trusted_member_id: The user being trusted

        Returns:
            True if successful
        """
        try:
            if member_id not in self.members or trusted_member_id not in self.members:
                logger.error(f"One or both members not found")
                return False

            member = self.members[member_id]
            trusted_member = self.members[trusted_member_id]

            # Both must be Tier 4+ for sharing
            if member.get('access_tier', 1) < 4 or trusted_member.get('access_tier', 1) < 4:
                logger.warning(f"Both members must be Tier 4+ for trusted sharing")
                return False

            # Add bidirectional trust
            if 'trusted_users' not in member:
                member['trusted_users'] = []
            if trusted_member_id not in member['trusted_users']:
                member['trusted_users'].append(trusted_member_id)

            if 'trusted_users' not in trusted_member:
                trusted_member['trusted_users'] = []
            if member_id not in trusted_member['trusted_users']:
                trusted_member['trusted_users'].append(member_id)

            # Save changes
            self.update_member(member_id, {'trusted_users': member['trusted_users']})
            self.update_member(trusted_member_id, {'trusted_users': trusted_member['trusted_users']})

            logger.info(f"Added trusted connection: {member_id} <-> {trusted_member_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding trusted user: {e}", exc_info=True)
            return False

    def get_accessible_thread_ids(self, member_id: str) -> List[str]:
        """
        Get all thread_ids a member can access based on sharing mode

        Args:
            member_id: Member ID

        Returns:
            List of thread_ids the member can access
        """
        try:
            member = self.members.get(member_id)
            if not member:
                logger.error(f"Member not found: {member_id}")
                return []

            accessible = [member.get('thread_id')]  # Always own thread
            mode = member.get('memory_sharing_mode', 'isolated')
            tier = member.get('access_tier', 1)

            if tier < 4:
                # Tier < 4: only own memory
                return accessible

            if mode == "trusted":
                # Add trusted users' threads
                for trusted_id in member.get('trusted_users', []):
                    trusted = self.members.get(trusted_id)
                    if trusted:
                        accessible.append(trusted.get('thread_id'))

            elif mode == "pooled":
                # Add all users at same tier's threads
                pool_tier = member.get('pooled_tier', tier)
                for other_member in self.members.values():
                    if other_member.get('access_tier') == pool_tier and other_member.get('memory_sharing_mode') == 'pooled':
                        if 'thread_id' in other_member:
                            accessible.append(other_member.get('thread_id'))

            return list(set(accessible))  # Remove duplicates

        except Exception as e:
            logger.error(f"Error getting accessible threads: {e}", exc_info=True)
            return []

    def add_admin_flag(self, member_id: str, note: str) -> bool:
        """
        Add admin observation flag (read-only, non-modifying)

        Args:
            member_id: Member ID
            note: Admin observation note

        Returns:
            True if successful
        """
        try:
            if member_id not in self.members:
                logger.error(f"Member not found: {member_id}")
                return False

            member = self.members[member_id]
            if 'admin_flags' not in member:
                member['admin_flags'] = []

            member['admin_flags'].append({
                'note': note,
                'timestamp': datetime.now().isoformat(),
                'admin_id': 'system'  # Would be replaced with actual admin ID
            })

            self.update_member(member_id, {'admin_flags': member['admin_flags']})
            logger.info(f"Added admin flag for {member_id}: {note}")
            return True

        except Exception as e:
            logger.error(f"Error adding admin flag: {e}", exc_info=True)
            return False

    def get_all_members(self) -> List[Dict]:
        """Get all members"""
        return list(self.members.values())
    
    def delete_member(self, member_id: str) -> bool:
        """Delete member (archives their data)"""
        try:
            if member_id not in self.members:
                logger.error(f"Member not found: {member_id}")
                return False
            
            # Archive member data
            archive_file = self.data_dir / f"deleted_member_{member_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(archive_file, 'w', encoding='utf-8') as f:
                json.dump(self.members[member_id], f, indent=2)
            
            # Remove from active database
            del self.members[member_id]
            
            # Save
            self._save_members_db({
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "version": "1.0",
                    "total_members": len(self.members),
                    "last_updated": datetime.now().isoformat()
                },
                "members": self.members
            })
            
            # Log transaction
            self._log_transaction({
                "type": "member_deleted",
                "member_id": member_id,
                "timestamp": datetime.now().isoformat(),
                "archived_to": str(archive_file)
            })
            
            logger.info(f"Deleted member: {member_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting member: {e}", exc_info=True)
            return False
    
    def _deep_update(self, target: Dict, updates: Dict):
        """Deep update dictionary"""
        for key, value in updates.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value
    
    # ============================================
    # CARD OPERATIONS
    # ============================================
    
    def save_member_card(self, member_id: str, card_path: str) -> Optional[str]:
        """Save member's current card (archives old one if exists)"""
        try:
            # Get member data
            member = self.get_member(member_id)
            if not member:
                logger.error(f"Member not found: {member_id}")
                return None
            
            # Check if member has existing card
            existing_card = member.get('card_data', {}).get('current_card_path')
            if existing_card and Path(existing_card).exists():
                # Archive old card
                old_card_path = Path(existing_card)
                archive_filename = f"{member_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{old_card_path.name}"
                archive_path = self.archived_cards_dir / archive_filename
                
                import shutil
                shutil.move(str(old_card_path), str(archive_path))
                logger.info(f"Archived old card: {archive_path}")
            
            # Copy new card to member cards directory
            new_card_path = self.cards_dir / f"{member_id}_current.png"
            import shutil
            shutil.copy(card_path, str(new_card_path))
            
            # Update member data
            self.update_member(member_id, {
                'card_data': {
                    'current_card_path': str(new_card_path),
                    'last_updated': datetime.now().isoformat(),
                    'valid': True  # Assume valid until validation check
                }
            })
            
            logger.info(f"Saved new card for member: {member_id}")
            return str(new_card_path)
            
        except Exception as e:
            logger.error(f"Error saving member card: {e}", exc_info=True)
            return None
    
    def get_member_card_path(self, member_id: str) -> Optional[str]:
        """Get path to member's current card"""
        member = self.get_member(member_id)
        if member:
            return member.get('card_data', {}).get('current_card_path')
        return None
    
    # ============================================
    # BOOKS OPERATIONS
    # ============================================
    
    def add_book(self, book_data: Dict) -> bool:
        """Add book to inventory"""
        try:
            book_id = book_data.get('book_id')
            if not book_id:
                logger.error("Book ID missing in book_data")
                return False
            
            # Add to memory
            self.books[book_id] = book_data
            
            # Save to disk
            self._save_books_db({
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "version": "1.0",
                    "total_books": len(self.books),
                    "last_updated": datetime.now().isoformat()
                },
                "books": self.books
            })
            
            logger.info(f"Added book: {book_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding book: {e}", exc_info=True)
            return False
    
    def update_book(self, book_id: str, updates: Dict) -> bool:
        """Update book inventory"""
        try:
            if book_id not in self.books:
                logger.error(f"Book not found: {book_id}")
                return False
            
            self._deep_update(self.books[book_id], updates)
            
            self._save_books_db({
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "version": "1.0",
                    "total_books": len(self.books),
                    "last_updated": datetime.now().isoformat()
                },
                "books": self.books
            })
            
            logger.info(f"Updated book: {book_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating book: {e}", exc_info=True)
            return False
    
    def get_book(self, book_id: str) -> Optional[Dict]:
        """Get book data"""
        return self.books.get(book_id)
    
    def get_all_books(self) -> List[Dict]:
        """Get all books"""
        return list(self.books.values())
    
    def search_books(self, query: str) -> List[Dict]:
        """Search books by title, author, or ISBN"""
        query_lower = query.lower()
        results = []
        
        for book in self.books.values():
            if (query_lower in book.get('title', '').lower() or
                query_lower in book.get('author', '').lower() or
                query_lower in book.get('isbn', '').lower()):
                results.append(book)
        
        return results
    
    # ============================================
    # RENTAL OPERATIONS
    # ============================================
    
    def calculate_overdue_fee(self, due_date: str, return_date: Optional[str] = None) -> float:
        """
        Calculate overdue fees
        $1 per day, starting at midday after due date
        """
        try:
            due_dt = datetime.fromisoformat(due_date)
            return_dt = datetime.fromisoformat(return_date) if return_date else datetime.now()
            
            # Calculate overdue from midday (12:00) of day after due date
            overdue_start = due_dt.replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1)
            
            if return_dt <= overdue_start:
                return 0.0
            
            # Calculate days overdue (using ceiling to charge partial days)
            overdue_delta = return_dt - overdue_start
            days_overdue = math.ceil(overdue_delta.total_seconds() / 86400)  # 86400 seconds in a day
            
            return float(days_overdue * 1.00)
            
        except Exception as e:
            logger.error(f"Error calculating overdue fee: {e}", exc_info=True)
            return 0.0
    
    def is_overdue(self, due_date: str) -> bool:
        """Check if rental is overdue"""
        try:
            due_dt = datetime.fromisoformat(due_date)
            overdue_start = due_dt.replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return datetime.now() > overdue_start
        except:
            return False
    
    def get_member_rentals(self, member_id: str) -> List[Dict]:
        """Get all rentals for a member"""
        member = self.get_member(member_id)
        if member:
            return member.get('rentals', [])
        return []
    
    def add_rental(self, member_id: str, rental_data: Dict) -> bool:
        """Add rental to member's account"""
        try:
            member = self.get_member(member_id)
            if not member:
                logger.error(f"Member not found: {member_id}")
                return False
            
            # Initialize rentals list if doesn't exist
            if 'rentals' not in member:
                member['rentals'] = []
            
            # Add rental
            member['rentals'].append(rental_data)
            
            # Update book availability
            book_id = rental_data.get('book_id')
            if book_id:
                book = self.get_book(book_id)
                if book:
                    available = book.get('available_copies', 0)
                    copies_out = book.get('copies_out', 0)
                    self.update_book(book_id, {
                        'available_copies': max(0, available - 1),
                        'copies_out': copies_out + 1
                    })
            
            # Save member
            self.update_member(member_id, {'rentals': member['rentals']})
            
            logger.info(f"Added rental for member: {member_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding rental: {e}", exc_info=True)
            return False
    
    def return_rental(self, member_id: str, rental_id: str) -> Dict:
        """Process book return and calculate fees"""
        try:
            member = self.get_member(member_id)
            if not member:
                return {"success": False, "error": "Member not found"}
            
            # Find rental
            rentals = member.get('rentals', [])
            rental = None
            rental_index = None
            
            for i, r in enumerate(rentals):
                if r.get('rental_id') == rental_id:
                    rental = r
                    rental_index = i
                    break
            
            if not rental:
                return {"success": False, "error": "Rental not found"}
            
            # Calculate fees
            due_date = rental.get('due_date')
            return_date = datetime.now().isoformat()
            overdue_fee = self.calculate_overdue_fee(due_date, return_date)
            
            # Update rental
            rental['return_date'] = return_date
            rental['overdue_fee'] = overdue_fee
            rental['status'] = 'returned'
            
            # Update book availability
            book_id = rental.get('book_id')
            if book_id:
                book = self.get_book(book_id)
                if book:
                    available = book.get('available_copies', 0)
                    copies_out = book.get('copies_out', 0)
                    self.update_book(book_id, {
                        'available_copies': available + 1,
                        'copies_out': max(0, copies_out - 1)
                    })
            
            # Save member
            self.update_member(member_id, {'rentals': rentals})
            
            logger.info(f"Processed return for member: {member_id}, Fee: ${overdue_fee:.2f}")
            
            return {
                "success": True,
                "overdue_fee": overdue_fee,
                "return_date": return_date,
                "was_overdue": overdue_fee > 0
            }
            
        except Exception as e:
            logger.error(f"Error processing return: {e}", exc_info=True)
            return {"success": False, "error": str(e)}


# Singleton instance
_db_instance = None

def get_database() -> DatabaseManager:
    """Get singleton database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
