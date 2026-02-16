# RedVerse Authentication & Memory Architecture
## Codename: **The Crimson Gate Protocol**

> A phased engineering spec for implementing per-user JSONL memory, tiered access control, RedSeal-based authentication, and cross-site AI continuity across the RedVerse ecosystem.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER JOURNEY                                  │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │ Aurora Card   │───▶│   Obelisk    │───▶│  index_entrance.html │   │
│  │ Generator GUI │    │   Customs    │    │  (Church Entrance)   │   │
│  │ (Account +    │    │ (Validates   │    │                      │   │
│  │  Image Gen +  │    │  RedSeal +   │    │  ┌────────┐ ┌─────┐ │   │
│  │  RedSeal)     │    │  Redirects)  │    │  │E-Drive │ │Oracle│ │   │
│  └──────────────┘    └──────────────┘    │  │(Tier N) │ │(T N)│ │   │
│                                           │  └────────┘ └─────┘ │   │
│                                           └──────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ ADMIN GUI (Server-Side, Crimson Only)                        │    │
│  │ • View/Edit/Approve/Deny all members                         │    │
│  │ • Upgrade/Downgrade tiers (1-7)                              │    │
│  │ • View all JSONL memory logs                                 │    │
│  │ • Live-updating dashboard                                    │    │
│  └──────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Refactor Aurora Card Generator GUI

**Goal:** Restructure the existing `aurora_pyqt6_main.py` into a cleaner multi-tab interface that separates account creation from card generation.

### Tab 1: Account Setup
This is the **identity forge** — where a user's data enters the system.

**Fields to collect:**
- Display Name (required)
- Email (required, used as unique identifier)
- Optional: Bio, Location, Interests, Avatar preference
- Auto-generated: `member_id` (hash-based, from `member_manager.py`), `thread_id` (UUID, for JSONL recall), `created_at` timestamp

**On Submit:**
1. Create member record via `MemberManager.create_new_member()`
2. Store in `DatabaseManager` (JSON + JSONL redundancy — already implemented)
3. Generate a `thread_id` (UUID4) — this is the key for per-user JSONL memory files
4. Assign **Tier 1** by default (bare experience)
5. Persist: `data/members_database.json` and `data/members_database.jsonl`

**Data structure addition to member schema:**
```python
{
    "member_id": "AUR-XXXX-XXXX",
    "thread_id": "uuid4-string",          # NEW — links to JSONL memory
    "access_tier": 1,                      # NEW — 1 through 7
    "tier_name": "Wanderer",               # NEW — human-readable tier label
    "seal_status": "unsigned",             # unsigned | pending | complete
    "seal_verification_layer": None,       # populated after verification
    "oracle_context": {},                  # preloaded context for Oracle
    "edrive_context": {},                  # preloaded context for E-Drive
    # ... existing fields from member_manager.py
}
```

### Tab 2: Card Image Generation
This is the **visual identity** — the aesthetic card face.

**Backend selector (dropdown or radio group):**
- Stable Diffusion (localhost:7860, existing implementation)
- OpenAI DALL-E (API key required)
- Grok Image Gen (API key required)
- Midjourney (API key required)
- Custom Endpoint (user provides URL + optional API key)

**API key management:**
- Use existing `api_config_manager.py` (Fernet + PBKDF2 encrypted storage)
- Each endpoint stores: `{name, url, api_key_encrypted, model, default_params}`
- Tab shows a sub-panel for "Configure Endpoints" with add/edit/delete

**Image generation flow:**
1. User writes/adjusts the **positive prompt** (free text)
2. **Negative prompt** is locked/hidden (set by system defaults per backend)
3. All other settings (steps, CFG, sampler, dimensions) are **locked to defaults** — user cannot modify
4. User clicks "Generate" → image appears in preview
5. User can **re-roll** (regenerate with same or tweaked prompt) unlimited times
6. User clicks **"Accept Image"** → proceeds to RedSeal compositing

**What the user CANNOT touch:**
- Negative prompt
- Steps, CFG scale, sampler
- Image dimensions (locked to card format, e.g. 512×768)
- Seed (randomized each roll)

### Tab 3: RedSeal Application (Post-Accept)
Once the user accepts their card image, this phase is **automatic**:

1. **Resize RedSeal.png** to 100×100 (via `SealCompositor`)
2. **Embed account data** into the RedSeal pixels using `MutableCardSteganography`:
   - `member_id`, `thread_id`, `access_tier`, `email_hash`, `created_at`
   - `crimson_collective` seal object (sigil, authority, generation)
3. **Composite the embedded seal** onto the bottom of the card image
4. **Save the sealed card** to `data/member_cards/{member_id}_card.png`
5. Update member record: `seal_status = "pending"`

**The seal is now "pending" — not yet "complete."**

### The Verification Layer (Seal Completion)
A second steganographic layer is added to make the seal "complete":

1. After RedSeal is appended and embedded, a **verification hash** is computed:
   ```python
   verification_hash = sha256(member_id + thread_id + seal_sigil + timestamp)
   ```
2. This hash is embedded as a **secondary layer** in the RedSeal region
3. Member record updated: `seal_status = "complete"`, `seal_verification_layer = verification_hash`
4. The card is now **Obelisk-ready**

---

## Phase 2: Per-User JSONL Memory Database

**Goal:** Every user gets their own conversation memory file, queryable by both E-Drive and Oracle.

### File Structure
```
memory/
├── threads/
│   ├── {thread_id_1}.jsonl      # User 1's conversation history
│   ├── {thread_id_2}.jsonl      # User 2's conversation history
│   └── ...
├── session_{session_id}.jsonl    # Existing session files (unchanged)
└── trajectory_{session_id}.json  # Existing trajectory files (unchanged)
```

### JSONL Entry Format
Each line in a user's `{thread_id}.jsonl`:
```json
{
    "event_id": "uuid4",
    "timestamp": "ISO-8601",
    "source": "edrive|oracle",
    "role": "user|assistant|system",
    "content": "the message text",
    "emotion_state": {"primary": "joy", "intensity": 0.7},
    "metadata": {
        "page": "edrive|oracle|redverse",
        "session_id": "current-session-uuid",
        "tier_at_time": 3,
        "model": "CrimsonDragonX7/Oracle:latest"
    }
}
```

### Memory Bridge Integration
Extend existing `memory_bridge.py` with:

```python
class UserMemoryBridge(MemoryBridge):
    """Per-user memory that persists across sessions and pages."""
    
    def __init__(self, thread_id: str, module_name: str = "EDrive"):
        super().__init__(module_name=module_name)
        self.thread_id = thread_id
        self.user_memory_file = os.path.join(
            MEMORY_DIR, "threads", f"{thread_id}.jsonl"
        )
    
    def load_user_context(self, last_n: int = 50) -> List[Dict]:
        """Load last N events for this user across all pages."""
        # Returns conversation history for prompt injection
    
    def store_user_event(self, event: Dict):
        """Append event to user's JSONL file."""
        # Writes to threads/{thread_id}.jsonl
    
    def get_cross_site_summary(self) -> str:
        """Generate a summary of user's activity across E-Drive and Oracle."""
        # Used for the AI's "awareness" of the user between pages
```

### Admin Visibility
- **Admin (Crimson):** Can read ALL user JSONL files, search across them, view emotional trajectories
- **Regular users:** Can only trigger reads of their OWN thread_id (enforced server-side)

---

## Phase 3: 7-Tier Access System

**Goal:** Placeholder tier structure with escalating access. Tier 1 is default, Tier 7 is "Inner Sanctum."

| Tier | Name | Access Level | Description |
|------|------|-------------|-------------|
| 1 | Wanderer | Bare | Current default experience as-is |
| 2 | Initiate | Basic | Basic Oracle + E-Drive chat, limited history |
| 3 | Acolyte | Standard | Full chat, emotion tracking visible |
| 4 | Keeper | Enhanced | Cross-site continuity active, custom prompts |
| 5 | Sentinel | Advanced | Advanced Soul Stacker configs, priority |
| 6 | Archon | Elevated | Full memory persistence, custom transitions |
| 7 | Inner Sanctum | Full | Everything. Admin-adjacent visibility. Deep lore. |

### Implementation
```python
TIER_CONFIG = {
    1: {"name": "Wanderer",      "memory_depth": 0,   "cross_site": False, "custom_soul": False},
    2: {"name": "Initiate",      "memory_depth": 10,  "cross_site": False, "custom_soul": False},
    3: {"name": "Acolyte",       "memory_depth": 25,  "cross_site": False, "custom_soul": False},
    4: {"name": "Keeper",        "memory_depth": 50,  "cross_site": True,  "custom_soul": False},
    5: {"name": "Sentinel",      "memory_depth": 100, "cross_site": True,  "custom_soul": True},
    6: {"name": "Archon",        "memory_depth": 500, "cross_site": True,  "custom_soul": True},
    7: {"name": "Inner Sanctum", "memory_depth": -1,  "cross_site": True,  "custom_soul": True},
    # memory_depth: -1 means unlimited
}
```

**Where tiers are enforced:**
- `serve_edrive.py` (or equivalent backend): checks `access_tier` from session, limits features
- `EDrive.html` / `oracle.html`: client-side feature gating (UI elements hidden/shown)
- `memory_bridge.py`: `load_user_context(last_n=TIER_CONFIG[tier]["memory_depth"])`

---

## Phase 4: Obelisk Customs → index_entrance.html Flow

**Goal:** RedSeal-authenticated card → Obelisk validates → redirects to index_entrance.html with session context.

### Flow
1. User presents card to Obelisk Customs (existing `obelisk_customs.py` or web version)
2. Obelisk extracts steganography data, validates:
   - Crimson Collective seal present
   - Verification layer intact
   - `member_id` and `thread_id` match database
3. If valid:
   - Generate a **session token** (JWT or signed cookie)
   - Token contains: `{member_id, thread_id, access_tier, tier_name, timestamp, signature}`
   - Redirect to `index_entrance.html?token={session_token}`
4. `index_entrance.html` reads the token, stores in `sessionStorage`
5. When loading `redverse.html` (via iframe), passes token to child
6. E-Drive and Oracle read the token to:
   - Load user's JSONL memory via `thread_id`
   - Apply tier-based feature gating
   - Address user by name with continuity awareness

### Web-Based Obelisk (New)
For the web flow, create a lightweight HTML page (`obelisk_web.html`) that:
1. Shows a card upload zone (drag-and-drop or file picker)
2. Sends the image to the backend for steganographic extraction
3. Backend validates and returns a session token
4. Client-side redirect to `index_entrance.html`

---

## Phase 5: Cross-Site AI Continuity

**Goal:** Both Oracle and E-Drive address the user as if the AI "follows" them between pages.

### How It Works
When a user with an active session navigates from Oracle to E-Drive (or vice versa):

1. The target page loads the session token from `sessionStorage`
2. Fetches the user's recent JSONL history (last N events based on tier)
3. Injects a **continuity prompt** into the AI's system context:

```
[CONTINUITY CONTEXT]
User: {display_name} (Tier {tier}: {tier_name})
Thread: {thread_id}
Last interaction: {source} at {timestamp}
Recent summary: {cross_site_summary}
Emotional trajectory: {recent_emotions}

You have been conversing with this user across multiple interfaces.
Acknowledge continuity naturally — do not break immersion.
Reference prior topics organically when relevant.
```

4. The AI responds as though it has seamless awareness
5. New messages are appended to the same `{thread_id}.jsonl`

**Important:** This is prompt-engineered continuity, not actual cross-process awareness. The JSONL file and summary injection create the *illusion* of a persistent, cross-site AI presence.

---

## Phase 6: Admin GUI (Server-Side)

**Goal:** A server-side admin panel accessible only to Crimson for managing all member data.

### Technical Approach
- **Framework:** PyQt6 desktop app (extends existing `member_manager_gui.py`)
- **OR** Flask/FastAPI web dashboard (if preferred for remote access)
- **Access:** Localhost only, or password-protected if web-based

### Features

**Dashboard Tab:**
- Total members count, active sessions, tier distribution chart
- Recent activity feed (last 50 events across all users)
- Live-updating: polls database every 5 seconds when open

**Members Tab:**
- Searchable/sortable member list
- Per-member: view profile, card image, tier, seal status
- Actions: Approve, Deny, Upgrade Tier, Downgrade Tier, Suspend, Delete
- Inline editing of member fields

**Memory Viewer Tab:**
- Select a user → view their complete JSONL history
- Filter by: source (edrive/oracle), date range, emotion
- Search across ALL user memories (admin privilege)
- Export user memory as JSONL download

**Tier Management Tab:**
- Batch upgrade/downgrade
- Set custom tier permissions per user (override defaults)
- Schedule tier changes (e.g., "upgrade to Tier 3 on March 1st")

**Live Update Behavior:**
- On open: full database reload
- While open: poll for changes every 5 seconds
- New members, tier changes, new activity highlighted
- Notification badge for pending approvals

---

## Phase Summary & Build Order

| Phase | What | Priority | Dependencies |
|-------|------|----------|-------------|
| 1 | Refactor Aurora GUI (Account + Image Gen + RedSeal) | **HIGH** | Existing Aurora codebase |
| 2 | Per-User JSONL Memory System | **HIGH** | Phase 1 (needs thread_id) |
| 3 | 7-Tier Access Config | **MEDIUM** | Phase 1 (needs member schema) |
| 4 | Obelisk → index_entrance.html Flow | **MEDIUM** | Phases 1 + 3 |
| 5 | Cross-Site AI Continuity | **MEDIUM** | Phases 2 + 4 |
| 6 | Admin GUI | **LOW** | All phases (uses everything) |

### Recommendation: Start with Phase 1
The Aurora GUI refactor is the foundation. Everything else depends on having proper account creation, image generation with backend flexibility, and the two-layer RedSeal verification. Once Phase 1 is solid, Phases 2 and 3 can be done in parallel, and the rest cascades from there.

---

## Existing Code to Leverage (Don't Reinvent)

| Module | Already Handles | Extend For |
|--------|----------------|------------|
| `member_manager.py` | Member creation, schema, tier assignment | Add `thread_id`, `access_tier` (1-7), `seal_status` |
| `database_manager.py` | JSON + JSONL storage, transactions | Add `threads/` directory management |
| `seal_compositor.py` | RedSeal resize, embed, composite | Add verification layer (second embed pass) |
| `mutable_steganography.py` | Embed/extract data in images | No changes needed — already robust |
| `card_scanner.py` | Seal detection, data extraction | Extend for verification layer check |
| `obelisk_customs.py` | Card validation, mark appending | Add session token generation, web redirect |
| `memory_bridge.py` | Session events, emotional tracking | Extend with `UserMemoryBridge` for per-user persistence |
| `api_config_manager.py` | Encrypted API key storage | Add presets for OpenAI, Grok, Midjourney endpoints |
| `aurora_pyqt6_main.py` | Card generation GUI | Refactor into tabbed Account/Generate/Seal interface |
| `member_manager_gui.py` | Admin panel for members | Extend with memory viewer, tier management, live updates |

---

## Security Boundaries

| Data | Client-Side Knows | Server-Side Only |
|------|-------------------|-----------------|
| `member_id` | ✅ (in session token) | Full record |
| `thread_id` | ✅ (in session token) | All thread files |
| `access_tier` | ✅ (for UI gating) | Tier override configs |
| `display_name` | ✅ (for personalization) | Email, phone, address |
| Memory (own) | ✅ (via API, own thread only) | All users' memory |
| Memory (others) | ❌ Never | Admin only |
| Seal verification hash | ❌ Never | Database + embedded |
| API keys | ❌ Never | Encrypted in config/ |

---

## Notes for the Coding Agent

1. **Don't nuke existing functionality.** The Aurora card generator, Obelisk customs, and member manager all work. We're extending, not rewriting.

2. **The RedSeal two-layer embed is the authentication "password."** Think of it as: Layer 1 = account data. Layer 2 = verification signature. Both must be present and matching for Obelisk to approve.

3. **JSONL is the memory format.** One file per user. Append-only during conversations. The `thread_id` in the member record is the filename (without extension).

4. **Tiers are placeholders.** Only Tier 1 (default, bare) needs to *do* anything right now. The rest are config entries waiting for future content. But the gating logic should be in place.

5. **Cross-site continuity is an illusion.** We inject recent memory into the system prompt. The AI doesn't actually "follow" anyone — it reads the JSONL context and plays the role. But to the user, the experience should feel seamless.

6. **Admin GUI is Crimson-only.** No web-facing admin panel. Either local PyQt6 app or localhost-only web dashboard. Never exposed to the internet.

7. **The user image generation re-roll loop is important.** They should be able to generate → preview → tweak prompt → regenerate as many times as they want before accepting. Only after acceptance does the RedSeal get applied.
