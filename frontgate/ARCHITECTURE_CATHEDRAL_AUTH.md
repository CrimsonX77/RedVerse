# The Cathedral Registry — Architecture Blueprint
## Per-User Memory + Gate-Based Access for The RedVerse

---

## Overview

The RedVerse becomes a **living cathedral** that remembers its visitors. Supabase provides authentication, per-user persistent memory, and tier-gated access — all from a static GitHub Pages frontend with zero backend server.

---

## Tier System: The Covenant Ranks

| Rank | Access Level | Requirements |
|------|-------------|--------------|
| **Wanderer** | Church entrance, hero page, public map overview | No account needed |
| **Acolyte** | Full saga details, cosmology, Sable remembers you | Free signup |
| **Devotee** | Private Sable mode, deep lore, full memory continuity | Stripe subscription |
| **Crimson Circle** | Aurora card verification, exclusive content, admin lore | Devotee + Aurora card scan |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  GitHub Pages (Static)                    │
│                                                          │
│  index_entrance.html ──→ redverse.html ──→ EDrive.html  │
│       (doors)              (map/lore)      (Sable chat)  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │            redverse-auth.js (new)                 │   │
│  │  • Supabase client initialization                 │   │
│  │  • Auth state management                          │   │
│  │  • Gate enforcement (DOM-level content locking)   │   │
│  │  • Memory read/write API                          │   │
│  │  • Tier resolution                                │   │
│  └──────────────────────────┬───────────────────────┘   │
│                              │                            │
└──────────────────────────────┼────────────────────────────┘
                               │ HTTPS (Supabase JS Client)
                               ▼
┌─────────────────────────────────────────────────────────┐
│                    Supabase (Free Tier)                   │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │    Auth      │  │  Database   │  │ Row-Level       │  │
│  │             │  │  (Postgres)  │  │ Security (RLS)  │  │
│  │ • Email/pw  │  │             │  │                  │  │
│  │ • OAuth     │  │ • profiles  │  │ Users can only   │  │
│  │ • Magic     │  │ • memory    │  │ read/write their │  │
│  │   links     │  │ • tiers     │  │ own data         │  │
│  └─────────────┘  └─────────────┘  └────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │          Edge Functions (optional later)           │   │
│  │  • Stripe webhook → update tier                    │   │
│  │  • Aurora card verification API                    │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Database Schema

### `profiles` table
Created automatically on user signup via trigger.

```sql
create table public.profiles (
  id uuid references auth.users on delete cascade primary key,
  display_name text,
  title text default 'Wanderer',           -- Covenant rank title
  tier text default 'wanderer' check (tier in ('wanderer','acolyte','devotee','crimson_circle')),
  aurora_card_id text,                      -- Linked Aurora card sigil (optional)
  first_visit timestamptz default now(),
  last_visit timestamptz default now(),
  visit_count integer default 1,
  created_at timestamptz default now()
);

-- RLS: users can only read/update their own profile
alter table public.profiles enable row level security;

create policy "Users can view own profile"
  on profiles for select using (auth.uid() = id);

create policy "Users can update own profile"
  on profiles for update using (auth.uid() = id);
```

### `memory_events` table
Per-user session memory — mirrors MemoryBridge's event structure.

```sql
create table public.memory_events (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  session_id text not null,
  event_type text not null,                 -- 'message', 'emotion_shift', 'saga_visit', 'gate_unlock'
  content jsonb not null,                   -- Flexible payload
  emotional_state jsonb,                    -- E-Drive ring snapshot at time of event
  created_at timestamptz default now()
);

-- Index for fast per-user queries
create index idx_memory_user_id on memory_events(user_id);
create index idx_memory_session on memory_events(user_id, session_id);

-- RLS: users can only access their own memory
alter table public.memory_events enable row level security;

create policy "Users can read own memory"
  on memory_events for select using (auth.uid() = user_id);

create policy "Users can write own memory"
  on memory_events for insert with check (auth.uid() = user_id);
```

### `sable_context` table
Sable's compressed per-user relational context (what she "knows" about a visitor).

```sql
create table public.sable_context (
  user_id uuid references public.profiles(id) on delete cascade primary key,
  relationship_summary text,               -- Compressed narrative of relationship
  emotional_baseline jsonb,                -- Average emotional state across sessions
  interaction_count integer default 0,
  favorite_sagas text[],                   -- Which sagas they revisit
  last_topic text,                         -- Last thing discussed
  personality_notes text,                  -- Sable's observations about the visitor
  updated_at timestamptz default now()
);

-- RLS
alter table public.sable_context enable row level security;

create policy "Users can read own sable_context"
  on sable_context for select using (auth.uid() = user_id);

create policy "Users can upsert own sable_context"
  on sable_context for insert with check (auth.uid() = user_id);

create policy "Users can update own sable_context"
  on sable_context for update using (auth.uid() = user_id);
```

### Auto-create profile on signup (trigger)

```sql
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, display_name, tier)
  values (new.id, new.raw_user_meta_data->>'display_name', 'acolyte');
  
  insert into public.sable_context (user_id)
  values (new.id);
  
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
```

---

## Gate System: How Doors Lock and Unlock

The gate system works at the **DOM level** — content exists in the HTML but is sealed behind CSS classes and JS enforcement.

### Gate Classes

```html
<!-- This saga card is visible to all -->
<div class="saga-card" data-saga="fallings-rise">...</div>

<!-- This saga detail requires Acolyte tier -->
<div class="saga-card gate-acolyte" data-saga="mechaedo">
  <div class="gate-lock-overlay">
    <span class="gate-sigil">⛧</span>
    <span class="gate-text">Registry required to enter</span>
  </div>
  ...content...
</div>

<!-- This section requires Devotee tier -->
<div class="gate-devotee" data-gate="deep-lore">
  <div class="gate-lock-overlay">
    <span class="gate-sigil">🔒</span>
    <span class="gate-text">Devotee covenant required</span>
  </div>
  ...content...
</div>
```

### Gate Resolution Flow

```
User clicks gated element
        │
        ▼
  Is user authenticated?
        │
   NO ──┤──── YES
   │         │
   ▼         ▼
  Show    Check tier
  Registry  │
  Modal    tier >= required?
            │
       NO ──┤── YES
       │         │
       ▼         ▼
      Show     Unlock
      Upgrade   content,
      Modal     animate
                gate opening
```

### Gate UX: "Cathedral Registry" Modal

The auth modal is styled as a ritual — not a generic login form.

- **Header**: "The Cathedral Registry" in Cinzel
- **Subtext**: "Your name echoes in these halls. Register to be remembered."
- **Fields**: Display name (your title in the Church), email, password
- **Submit button**: "Inscribe My Name"
- **Social auth**: "Enter through another door" (Google, GitHub)
- **Visual**: Crimson border glow, vignette, subtle blood-drip animation on the edges

---

## Memory Flow: Making Sable Remember

### On Every Visit (Authenticated User)

```
1. Page loads → check Supabase auth session
2. If authenticated:
   a. Update profiles.last_visit and increment visit_count
   b. Fetch sable_context for this user
   c. Inject context into E-Drive system prompt:
      "This visitor is [name], title: [Acolyte]. 
       They have visited [N] times.
       Last topic: [topic]. 
       Sable's notes: [personality_notes].
       Favorite sagas: [sagas]."
3. During chat:
   a. Each message pair → write to memory_events
   b. Track emotional state via E-Drive ring snapshot
   c. Track saga visits → update sable_context.favorite_sagas
4. On session end / tab close:
   a. Compress session into sable_context update
   b. Update relationship_summary
```

### Sable's Memory Prompt Injection

```javascript
// Before each LLM call, inject relational context
const sableMemory = await getSableContext(userId);

const memoryPrompt = sableMemory ? `
[RELATIONAL MEMORY — This visitor has history with the Cathedral]
Visitor: ${profile.display_name} (${profile.title})
Visits: ${profile.visit_count} | First: ${profile.first_visit}
${sableMemory.relationship_summary || 'New soul. Treat with curious warmth.'}
${sableMemory.last_topic ? `Last discussed: ${sableMemory.last_topic}` : ''}
${sableMemory.personality_notes || ''}
${sableMemory.favorite_sagas?.length ? `Drawn to: ${sableMemory.favorite_sagas.join(', ')}` : ''}
` : '[No memory — first visit. Welcome this wanderer.]';
```

---

## File Changes Required

### New Files
- `redverse-auth.js` — Core auth/memory/gate module (~400 lines)
- `redverse-gate.css` — Gate overlay styles
- `supabase-setup.sql` — Database schema (copy from above)

### Modified Files
- `index_entrance.html` — Add Supabase CDN + auth script import
- `redverse.html` — Add gate classes to content, auth UI in nav, import auth module
- `EDrive.html` — Import auth module, inject memory context into LLM calls

### Unchanged
- All Python tools (Aurora, MemoryBridge, etc.) — remain desktop tools
- `support.html` — Stripe integration stays separate for now

---

## Implementation Priority

1. **Phase 1** (this session): `redverse-auth.js` core module + gate CSS + schema SQL
2. **Phase 2**: Integrate into redverse.html (gate saga details, add auth to nav)
3. **Phase 3**: Integrate into EDrive.html (Sable memory injection)
4. **Phase 4**: Stripe subscription for Devotee tier
5. **Phase 5**: Aurora card verification for Crimson Circle tier

---

## Security Notes

- Supabase anon key is safe to expose in client-side code (it's designed for this)
- RLS policies ensure users can only access their own data
- Tier upgrades should ONLY happen server-side (Edge Functions or Stripe webhooks)
- Never trust client-side tier claims for sensitive content
- Aurora card verification should happen via Edge Function, not client-side
