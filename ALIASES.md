# Privacy & Identity System - User-Controlled Preferences

Egregora supports user-controlled privacy and identity preferences through in-band commands sent in the WhatsApp group.

## Core Principles

1. **Privacy by Default**: All users anonymous (UUID) by default
2. **Opt-In Identity**: Aliases are optional and revocable
3. **Complete Opt-Out**: Users can remove ALL their data
4. **Social Transparency**: Commands visible to the whole group
5. **Immutable Storage**: Posts always use UUIDs (privacy-safe)

## The `/egregora` Prefix - Exclude Anything

**ANY message starting with `/egregora` is automatically excluded** from processing.

This serves dual purposes:
1. **Commands** - Control your privacy and identity
2. **Ad-hoc exclusion** - Mark specific messages as "don't include this"

### 💬 Ad-Hoc Message Exclusion

Prefix any message with `/egregora` to exclude it from blog posts:

```
User: /egregora This is private, don't include it in the blog
User: /egregora [sensitive financial discussion]
User: /egregora Just testing, ignore this
```

**These messages are removed from the DataFrame BEFORE any processing:**
- Never reach LLM
- Never in enrichment
- Never in posts
- Removed immediately, no persistence needed

**Use cases:**
- Private discussions you don't want in blog
- Sensitive topics (finances, health, personal)
- Meta-discussions about the blog itself
- Testing or debugging

---

## Commands

Participants can send commands in the WhatsApp group to control their data and identity:

### 🚫 Complete Opt-Out (Right to be Forgotten)
```
/egregora opt-out
```
**REMOVES ALL YOUR MESSAGES** from processing. This is immediate and persistent:
- All your messages filtered out BEFORE any processing
- Applies to current and future runs
- Your data never reaches LLM, enrichment, or posts
- Profile marked as "OPTED OUT"
- Reversible with `/egregora opt-in`

**When to use:**
- You don't want your messages in the blog
- GDPR-style "right to be forgotten"
- Privacy concerns

**Example Flow:**
```
User: /egregora opt-out
Pipeline: ⚠️ User a3f8c2b1 OPTED OUT - 47 messages removed
Result: Zero traces of you in posts
```

### ✅ Opt Back In
```
/egregora opt-in
```
Reverses opt-out. Your messages will be included in future runs.

---

### Set Alias
```
/egregora set alias "Franklin"
```
Sets display name to "Franklin". This is visible to the whole group (social transparency).

### Remove Alias
```
/egregora remove alias
```
Removes display name, reverting to UUID-only display.

### Set Bio
```
/egregora set bio "Python enthusiast, data nerd"
```
Adds a user-defined bio to profile.

### Set Links
```
/egregora set twitter "@franklindev"
/egregora set website "https://franklin.dev"
```
Adds social links to profile.

## How It Works

### 1. Command Detection (Parse Time)
Commands are extracted from messages after parsing:
```python
df = parse_export(export)
commands = extract_commands(df)  # Finds /egregora commands
process_commands(commands, profiles_dir)  # Updates profiles
```

### 2. Profile Storage (Mutable)
Aliases stored in `output/profiles/{uuid}.md`:
```markdown
# Profile: a3f8c2b1

## Display Preferences
- Alias: "Franklin" (set on 2025-01-15 14:32:00)
- Public: true

## User Bio
"Python enthusiast, data nerd"

(Set on 2025-01-15 14:32:00)

## Links
- Twitter: @franklindev
- Website: https://franklin.dev

## Writing Style
[LLM-generated profile content...]
```

### 3. Post Generation (UUID Only)
Writer ALWAYS uses UUIDs in post content:
```markdown
---
title: Python Tips
authors: [a3f8c2b1, b4e9d3c2]
---

# Python Optimization

Author a3f8c2b1 recently shared an interesting approach...
Author b4e9d3c2 added that we should also consider...
```

### 4. Rendering (Display Time)
Aliases resolved when displaying posts (NOT when storing):

**Option A: Static Site Generator (Hugo/Jekyll)**
```html
<!-- layouts/post.html -->
{{ range .Params.authors }}
  {{ $profile := readFile (printf "profiles/%s.md" .) }}
  {{ $alias := findRE "Alias: \"([^\"]+)\"" $profile }}
  {{ if $alias }}
    <span class="author">{{ index $alias 0 }} ({{ . }})</span>
  {{ else }}
    <span class="author">{{ . }}</span>
  {{ end }}
{{ end }}
```

**Option B: JavaScript (Client-Side)**
```javascript
// Load profiles
const profiles = await fetch('/profiles/index.json').then(r => r.json());

// Resolve UUIDs to display names
document.querySelectorAll('.author-uuid').forEach(elem => {
  const uuid = elem.dataset.uuid;
  const profile = profiles[uuid];

  if (profile && profile.alias) {
    elem.textContent = `${profile.alias} (${uuid})`;
  } else {
    elem.textContent = uuid;
  }
});
```

**Option C: Build Script (Python)**
```python
from egregora.profiler import get_author_display_name

def render_post_with_aliases(post_path: Path, profiles_dir: Path) -> str:
    """Render post with aliases replaced."""
    content = post_path.read_text()

    # Find all UUID references (8-char hex)
    uuid_pattern = re.compile(r'\b[a-f0-9]{8}\b')

    def replace_uuid(match):
        uuid = match.group(0)
        alias = get_author_display_name(uuid, profiles_dir)
        if alias != uuid:
            return f"{alias} ({uuid})"
        return uuid

    return uuid_pattern.sub(replace_uuid, content)
```

## Benefits

### 1. Revocable Identity
```bash
# Day 1: User sets alias
$ /egregora set alias "Franklin"
# Posts rendered: "Franklin (a3f8c2b1)"

# Day 30: User removes alias
$ /egregora remove alias
# Posts rendered: "a3f8c2b1"
# (Same markdown, different display!)
```

### 2. Privacy-Safe Storage
- Post markdown NEVER contains aliases
- Can archive/version control posts safely
- No need to "scrub" old posts if alias removed

### 3. Social Transparency
- Commands sent in group chat (everyone sees)
- Opt-in by design (explicit action required)
- No hidden surveillance

### 4. Immutable Posts
- Post content never changes
- Safe to cache, CDN, static hosting
- Alias changes update display automatically

## Example Flow

**Step 1: User sends command**
```
[WhatsApp Group]
Franklin: /egregora set alias "Franklin"
```

**Step 2: Pipeline processes**
```bash
$ egregora process export.zip
INFO: Found 1 egregora commands
INFO: Set alias 'Franklin' for a3f8c2b1
INFO: Processing 2025-01-15...
```

**Step 3: Profile updated**
```markdown
# Profile: a3f8c2b1

## Display Preferences
- Alias: "Franklin" (set on 2025-01-15 14:32:00)
- Public: true
```

**Step 4: Post generated (UUID only)**
```markdown
---
title: Python Tips
authors: [a3f8c2b1]
---

Author a3f8c2b1 shared interesting insights...
```

**Step 5: Display rendered**
```html
<article>
  <h1>Python Tips</h1>
  <p class="author">By Franklin (a3f8c2b1)</p>
  <p>Author <strong>Franklin</strong> <small>(a3f8c2b1)</small> shared interesting insights...</p>
</article>
```

**Step 6: User revokes (months later)**
```
[WhatsApp Group]
Franklin: /egregora remove alias
```

**Step 7: Display auto-updates**
```html
<p>Author <strong>a3f8c2b1</strong> shared interesting insights...</p>
```
Post markdown unchanged, display updates automatically!

## Implementation

Alias system is implemented in:
- `src/egregora/parser.py` - Command parsing
- `src/egregora/profiler.py` - Command processing, alias storage/retrieval
- `src/egregora/pipeline.py` - Command integration
- `src/egregora/writer.py` - Enforces UUID-only content

Rendering is left to your static site generator / build script / client-side JS.

## Privacy Model

**What's stored:**
- Post content: UUIDs only (a3f8c2b1)
- Profiles: Aliases + timestamps + metadata

**What's revocable:**
- Aliases (remove command)
- All profile metadata

**What's immutable:**
- Post markdown content
- Message history (anonymized)

**What's linkable:**
- UUID5 pseudonyms (deterministic per author)
- Aliases over time (stored in profile history)

**What's NOT stored:**
- Real names in post content
- Aliases in post content
- Phone numbers, emails, etc.

## Best Practices

1. **Never hardcode aliases in templates** - Always resolve dynamically
2. **Include UUID alongside alias** - For technical reference
3. **Handle missing profiles gracefully** - Fallback to UUID
4. **Document rendering approach** - So users understand privacy model
5. **Test alias removal** - Ensure displays update correctly

## Migration

If you have existing posts with aliases in content, you'll need to:
1. Replace all aliases with UUIDs using regex
2. Store alias→UUID mapping in profiles
3. Update renderer to use dynamic resolution

This is a one-time migration for privacy-safe storage.
