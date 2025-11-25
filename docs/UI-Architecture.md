# TFCBM UI Architecture Documentation

## Overview
This document provides a comprehensive breakdown of the TFCBM (The Fastest Clipboard Manager) user interface using professional UI/UX terminology. Use this as a reference for discussing UI components and modifications.

---

## Visual Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│ APPLICATION WINDOW (Adw.ApplicationWindow)                         │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ HEADER BAR (Adw.HeaderBar)                                      │ │
│ │ [Window Controls] [App Title]                    [Hamburger ☰]  │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ FILTER TOOLBAR (Sticky, Gtk.Box)                                │ │
│ │ [⚙] [Scrollable Filter Chips ──────────] [Clear] [Sort] [Top↑] │ │
│ │      Text  Images  URLs  Files  .pdf                            │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ TAB BAR (Adw.TabBar)                                            │ │
│ │ [Recently Copied] [Recently Pasted] [Settings] [Tags]           │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ CONTENT VIEWPORT (Adw.TabView → ScrolledWindow)                 │ │
│ │ ┌───────────────────────────────────────────────────────────┐   │ │
│ │ │ ITEM LIST (Gtk.ListBox)                                    │   │ │
│ │ │ ┌─────────────────────────────────────────────────────────┐ │   │ │
│ │ │ │ ITEM CARD (ClipboardItemRow)                            │ │   │ │
│ │ │ │ ┌─────────────────────────────────────────────────────┐ │ │   │ │
│ │ │ │ │ HEADER: [Timestamp]    [Copy][View][Save][Tags][×]  │ │ │   │ │
│ │ │ │ ├─────────────────────────────────────────────────────┤ │ │   │ │
│ │ │ │ │ CONTENT PREVIEW: [Text/Image/File display]          │ │ │   │ │
│ │ │ │ ├─────────────────────────────────────────────────────┤ │ │   │ │
│ │ │ │ │ TAG OVERLAY (Bottom left): Tag1 Tag2 Tag3          │ │ │   │ │
│ │ │ │ └─────────────────────────────────────────────────────┘ │ │   │ │
│ │ │ └─────────────────────────────────────────────────────────┘ │   │ │
│ │ │ [... more items ...]                                        │   │ │
│ │ │ [LOAD MORE SENTINEL] ← Infinite scroll trigger              │   │ │
│ │ └───────────────────────────────────────────────────────────┘   │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ QUICK FILTER PANEL (Sticky, Gtk.Box)                            │ │
│ │ Custom Tags: [Work] [Personal] [Code] [Screenshots] ...         │ │
│ │ (FlowBox - wraps horizontally, user tags only)                  │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Inventory & Terminology

### 1. **Application Window** (Root Container)
- **Widget Type:** `Adw.ApplicationWindow`
- **Purpose:** Main application container
- **Properties:**
  - Default size: 800×600px
  - Adaptive layout support
- **Code Reference:** `ui/main.py:3485` (ClipboardWindow class)

---

### 2. **Header Bar** (Primary Navigation)
- **Widget Type:** `Adw.HeaderBar`
- **Purpose:** Window controls and primary actions
- **Contents:**
  - **Title Widget:** Application name "TFCBM"
  - **Leading Controls:** Window decorations (minimize, maximize, close)
  - **Trailing Controls:** Hamburger menu (settings, about)
- **Code Reference:** `ui/main.py:1549`

---

### 3. **Filter Toolbar** (Secondary Navigation/Actions)
- **Widget Type:** `Gtk.Box` (horizontal)
- **Position:** Sticky (always visible at top)
- **CSS Class:** `.toolbar`
- **Purpose:** Content filtering and sorting controls
- **Code Reference:** `ui/main.py:2372`

#### 3.1. **Filter Toggle Button**
- **Widget Type:** `Gtk.ToggleButton`
- **Icon:** `⚙` (settings gear or filter funnel)
- **State:** Active/Inactive
- **Behavior:** Shows/hides system content type filters
- **Tooltip:** "Show/hide system filters"
- **Code Reference:** `ui/main.py:2388`

#### 3.2. **Filter Chips Container**
- **Outer Widget:** `Gtk.ScrolledWindow` (horizontal scroll only)
- **Inner Widget:** `Gtk.FlowBox`
- **Purpose:** Houses filter chips (pills)
- **Behavior:** Scrollable if chips overflow
- **Code Reference:** `ui/main.py:2407`

##### 3.2.1. **Filter Chip** (Pill Button)
- **Widget Type:** `Gtk.ToggleButton`
- **Variants:**
  - **System Filters:** Text, Images, URLs, Files
  - **Extension Filters:** .pdf, .jpg, .png, etc.
  - **Custom Tag Filters:** User-defined tags
- **Visual State:**
  - **Inactive:** Gray background
  - **Active:** Colored/highlighted
- **CSS Class:** `.pill`
- **Code Reference:** `ui/main.py:2442`

#### 3.3. **Clear Filters Button**
- **Widget Type:** `Gtk.Button`
- **Label:** "Clear All"
- **Behavior:** Deactivates all filter chips, reloads full item list
- **Code Reference:** `ui/main.py:2516`

#### 3.4. **Sort Toggle Button**
- **Widget Type:** `Gtk.ToggleButton`
- **Icon:** Sort ascending/descending
- **States:** Newest first (DESC) / Oldest first (ASC)
- **Scope:** Applies to copied items tab only
- **Code Reference:** `ui/main.py:2522`

#### 3.5. **Jump to Top Button**
- **Widget Type:** `Gtk.Button`
- **Icon:** Arrow up
- **Behavior:** Scrolls content viewport to top
- **Code Reference:** `ui/main.py:2531`

---

### 4. **Tab Bar** (View Switcher)
- **Widget Type:** `Adw.TabBar`
- **Associated:** `Adw.TabView`
- **Purpose:** Switch between different content views
- **Tabs:**
  1. **Recently Copied** (default, clipboard history)
  2. **Recently Pasted** (paste history)
  3. **Settings** (app configuration)
  4. **Tags** (tag management)
- **Code Reference:** `ui/main.py:1575`

---

### 5. **Content Viewport** (Main Content Area)
- **Widget Type:** `Adw.TabView` → `Gtk.ScrolledWindow`
- **Purpose:** Displays active tab content
- **Scroll Behavior:** Vertical scroll, infinite pagination
- **Code Reference:** `ui/main.py:1587`

---

### 6. **Item List** (Data Container)
- **Widget Type:** `Gtk.ListBox`
- **Purpose:** Displays clipboard items as rows
- **Selection Mode:** Single selection
- **Item Type:** `ClipboardItemRow` (custom widget)
- **Pagination:** Loads items in batches (default: 19 items per page)
- **Code Reference:** `ui/main.py:1605` (copied_listbox), `ui/main.py:1618` (pasted_listbox)

---

### 7. **Clipboard Item Card** (List Row)
- **Widget Type:** `ClipboardItemRow` (extends `Gtk.ListBoxRow`)
- **Purpose:** Displays individual clipboard entry
- **Dimensions:** Full width × Fixed height (configurable, default ~130px)
- **Visual Structure:** Card-based design with rounded corners
- **CSS Class:** `.clipboard-item-card`
- **Code Reference:** `ui/main.py:38`

#### 7.1. **Item Header** (Metadata Bar)
- **Widget Type:** `Gtk.Box` (horizontal)
- **Contents:**
  - **Timestamp Label:** Shows copy/paste time
  - **Action Button Group:** Copy, View, Save, Tags, Delete
- **Code Reference:** `ui/main.py:89`

##### 7.1.1. **Action Buttons** (Icon Buttons)
All buttons use **`Gtk.Button`** with **`.flat`** CSS class:

| Button | Icon | Tooltip | Action |
|--------|------|---------|--------|
| **Copy** | `edit-copy-symbolic` | "Copy to clipboard" | Copies item to clipboard |
| **View Full** | `zoom-in-symbolic` | "View full item" | Opens full-screen preview |
| **Save** | `document-save-symbolic` | "Save to file" | Export item to disk |
| **Manage Tags** | `tag-symbolic` | "Manage tags" | Open tag assignment popover |
| **Delete** | `user-trash-symbolic` | "Delete item" | Remove item from history |

**Code References:**
- Copy: `ui/main.py:113`
- View: `ui/main.py:124`
- Save: `ui/main.py:135`
- Tags: `ui/main.py:148`
- Delete: `ui/main.py:161`

#### 7.2. **Content Preview Area**
- **Widget Type:** Varies by content type
- **Purpose:** Shows preview of clipboard data
- **Types:**
  - **Text:** `Gtk.Label` (truncated with ellipsis)
  - **Image:** `Gtk.Picture` (thumbnail)
  - **File:** Icon + metadata (filename, size)
  - **URL:** `Gtk.Label` with link styling
- **Code Reference:** `ui/main.py:177-393`

#### 7.3. **Tag Display Overlay**
- **Widget Type:** `Gtk.Overlay` → `Gtk.Box` (horizontal)
- **Position:** Bottom left corner
- **Purpose:** Shows assigned custom tags
- **Contents:** Colored text labels (tag names)
- **Visibility:** Only shows non-system tags
- **Limit:** All tags (previously limited to 3)
- **Code Reference:** `ui/main.py:403`, `ui/main.py:457`

---

### 8. **Load More Sentinel** (Pagination Trigger)
- **Purpose:** Infinite scroll trigger point
- **Mechanism:** Intersection observer pattern (via scroll event)
- **Behavior:** Fetches next page when sentinel enters viewport
- **Code Reference:** `ui/main.py:2243` (_fetch_more_items)

---

### 9. **Quick Filter Panel** (Bottom Bar)
- **Widget Type:** `Gtk.Box` → `Gtk.FlowBox`
- **Position:** Sticky (always visible at bottom)
- **Purpose:** Quick access to tag-based filtering
- **Contents:** User-created tag pills (excludes system tags)
- **Behavior:**
  - Single-select or multi-select toggle
  - Filters item list by selected tags
- **Code Reference:** `ui/main.py:1662`, `ui/main.py:2839`

#### 9.1. **Tag Filter Pill**
- **Widget Type:** `Gtk.Button`
- **CSS Class:** `.pill`
- **Visual States:**
  - **Selected:** Colored background (25% opacity of tag color)
  - **Unselected:** Grayscale
- **Interaction:** Click to toggle selection
- **Code Reference:** `ui/main.py:2861`

---

## Data Flow & State Management

### Filter Application Flow
```
User Action (Filter Chip Toggle)
        ↓
_on_filter_toggled() → Updates self.active_filters (Set)
        ↓
_apply_filters() → Triggers DB reload
        ↓
_reload_current_tab() → Determines active tab
        ↓
WebSocket Request with filters parameter
        ↓
Server: get_history(filters=["text", "image", "MyTag"])
        ↓
Database: get_items(filters=["text", "image", "MyTag"])
        ↓
SQL WHERE clause construction
        ↓
Filtered results returned to UI
        ↓
Item List updated with filtered items
```

### Tag Display Flow
```
ClipboardItemRow.__init__()
        ↓
_load_item_tags() (async)
        ↓
WebSocket: get_item_tags(item_id)
        ↓
Server queries item_tags table
        ↓
Returns tag list (including system tags)
        ↓
_display_tags() (UI thread)
        ↓
Filters out system tags
        ↓
Displays all user tags as colored labels
```

---

## Interaction Patterns

### Primary Actions (High Frequency)
1. **Single Click on Item Card** → Copy to clipboard
2. **Double Click on Item Card** → Open full-screen preview
3. **Click Filter Chip** → Toggle filter, reload list
4. **Click Tag Pill** → Filter by tag
5. **Scroll to Bottom** → Load more items (infinite scroll)

### Secondary Actions (Medium Frequency)
1. **Click Copy Button** → Copy item
2. **Click View Button** → Full preview
3. **Click Save Button** → Export to file
4. **Click Tags Button** → Open tag management popover
5. **Click Delete Button** → Remove item (with confirmation)

### Tertiary Actions (Low Frequency)
1. **Click Sort Toggle** → Change sort order
2. **Click Clear Filters** → Reset all filters
3. **Click Jump to Top** → Scroll to top
4. **Click Filter Toggle** → Show/hide system filters

---

## Responsive Behavior

### Window Resizing
- **Filter Toolbar:** Chips scroll horizontally if overflow
- **Item Cards:** Width adapts to window width
- **Tag Display:** Wraps tags if space limited
- **Quick Filter Panel:** Tags wrap to multiple rows

### Content Overflow
- **Item List:** Vertical scroll
- **Filter Chips:** Horizontal scroll
- **Tag Overlay:** Natural text wrapping
- **Long Text Preview:** Ellipsis truncation

---

## Accessibility Features

### Keyboard Navigation
- **Tab:** Navigate between focusable elements
- **Enter/Space:** Activate focused item/button
- **Arrow Keys:** Navigate list items
- **Escape:** Close popovers/dialogs

### Screen Reader Support
- **Tooltips:** All buttons have descriptive tooltips
- **ARIA Labels:** Implicit via GTK widget hierarchy
- **Focus Indicators:** Visual focus states on interactive elements

---

## CSS Classes Reference

| Class | Applied To | Purpose |
|-------|-----------|---------|
| `.toolbar` | Filter bar, tag bar | Toolbar styling |
| `.pill` | Filter chips, tag buttons | Rounded pill appearance |
| `.flat` | Action buttons | Remove button background |
| `.clipboard-item-card` | Item card frame | Card styling |
| `.dim-label` | Timestamps | Reduced opacity text |
| `.caption` | Secondary text | Smaller font size |
| `.suggested-action` | Primary CTAs | Accent color styling |

---

## Component Naming Convention

When discussing UI elements, use this format:
- **Container Level:** "Filter Toolbar", "Quick Filter Panel"
- **Component Level:** "Filter Toggle Button", "Sort Toggle"
- **Element Level:** "Copy Action Button", "Tag Display Label"
- **State Level:** "Active Filter Chip", "Selected Tag Pill"

---

## File References

- **Main UI:** `ui/main.py`
- **Item Row:** `ui/main.py:38` (ClipboardItemRow class)
- **Main Window:** `ui/main.py:1457` (ClipboardWindow class)
- **Styles:** `ui/style.css`
- **Settings:** `settings.yml`

---

## Glossary

- **Chip:** Small, pill-shaped button (typically for filters/tags)
- **Pill:** Same as chip - rounded rectangular button
- **Card:** Container with visual elevation (shadow/border)
- **Toolbar:** Horizontal bar containing actions/controls
- **Panel:** Dedicated area for specific functionality
- **Overlay:** Widget positioned on top of another widget
- **Viewport:** Scrollable content area
- **Sentinel:** Invisible element used for scroll detection
- **CTA:** Call-to-action button
- **Toggle:** Button with on/off states

---

*Last Updated: 2025-11-23*
*Version: 1.0*
