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
