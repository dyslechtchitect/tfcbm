# TFCBM Documentation

This directory contains comprehensive documentation for the TFCBM (The Fastest Clipboard Manager) project.

## Available Documentation

### 1. **UI Architecture** (`UI-Architecture.md`)
Detailed breakdown of the user interface using professional UI/UX terminology.

**Contents:**
- Complete component inventory
- Visual hierarchy diagrams
- Interaction patterns
- Data flow documentation
- CSS class reference
- Accessibility features
- Keyboard shortcuts

**Use this when:**
- Discussing UI changes or features
- Understanding component relationships
- Referencing specific UI elements
- Planning new features

### 2. **UI Structure Diagram** (`ui-structure.svg`)
Visual SVG diagram showing the complete UI layout with labeled components.

**Features:**
- Color-coded component types
- Professional UI/UX naming
- Hierarchical layout
- Interactive element positioning

**Use this when:**
- Need a visual reference
- Explaining UI to others
- Planning layout changes
- Quick component lookup

## Quick Reference

### Common UI Terms We Use:

| Term | Meaning | Example |
|------|---------|---------|
| **Filter Toolbar** | Top sticky bar with filter controls | Where "Text", "Images" chips live |
| **Filter Chip** | Pill-shaped toggle button | "Text", "Images", ".pdf" buttons |
| **Quick Filter Panel** | Bottom sticky bar with tag pills | User tag buttons at bottom |
| **Item Card** | Individual clipboard item display | Each row in the list |
| **Content Viewport** | Scrollable main area | Where item cards scroll |
| **Action Button** | Icon button in item header | Copy, View, Save, Tags, Delete |
| **Tag Overlay** | Tag display at bottom left of item | Colored tag labels |

### File Structure:
```
docs/
├── README.md              # This file
├── UI-Architecture.md     # Complete UI documentation
└── ui-structure.svg       # Visual diagram
```

## Contributing to Documentation

When adding features:
1. Update `UI-Architecture.md` with new components
2. Update `ui-structure.svg` if layout changes
3. Use professional UI/UX terminology
4. Add code references

## Viewing the SVG

The SVG diagram can be viewed in:
- Any modern web browser
- VS Code (with SVG extension)
- GNOME Image Viewer
- Inkscape (for editing)

---

*For technical implementation details, see the main repository README.md*
