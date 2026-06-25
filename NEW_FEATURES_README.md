# 🎉 NEW FEATURES - Animated Mask Drawer v2.1

## ✨ What's New

### 1. **Orange Keyframes for Opacity Changes** 🟠
- **Visual Distinction**: Keyframes that only change opacity are now colored **ORANGE**
- **Blue Keyframes** remain for position, size, and rotation changes
- **Easier Timeline Reading**: Quickly identify animation types at a glance

#### How It Works:
- Position/size/rotation keyframes: **Blue** (#4a9eff)
- Opacity-only keyframes: **Orange** (#ff9944)
- Legend displayed in timeline sidebar

### 2. **Persistent Mask Saving** 💾
- **Auto-Save**: Masks are automatically saved to ComfyUI's temp directory
- **Auto-Load**: Previously drawn masks load automatically when you open the editor
- **No Data Loss**: Your work persists across ComfyUI sessions

#### Technical Details:
- Saved to: `ComfyUI/temp/animated_mask_data.json`
- Includes: All shapes, keyframes, properties, and stencil modes
- Loads automatically when editor opens

### 3. **Nuke Roto Import** 📋
The most powerful new feature - directly import shapes from Nuke!

#### How to Use:

**Method 1: Direct Paste**
1. In Nuke, select your Roto node
2. Copy the node (Ctrl+C)
3. In the Mask Editor, simply **paste** (Ctrl+V)
4. Import dialog opens automatically
5. Click "Import"

**Method 2: Manual Import**
1. Click **"📋 Import from Nuke"** button in sidebar
2. Paste your Nuke roto data
3. Click **"✓ Import"**

#### Supported Formats:

**Python Dictionary Format** (Recommended):
```python
{
  'curves': [
    {
      'name': 'Bezier1',
      'points': [
        {'x': 0.5, 'y': 0.3},
        {'x': 0.6, 'y': 0.4},
        {'x': 0.7, 'y': 0.5}
      ],
      'keyframes': [
        {
          'frame': 0,
          'points': [...]
        },
        {
          'frame': 30,
          'points': [...]
        }
      ]
    }
  ]
}
```

**JSON Format**:
```json
{
  "curves": [{
    "name": "Bezier1",
    "points": [
      {"x": 0.5, "y": 0.3},
      {"x": 0.6, "y": 0.4}
    ]
  }]
}
```

**Nuke TCL Format** (Basic Support):
```tcl
Bezier1 {
  {100 200}
  {150 250}
  {200 300}
}
```

#### Export from Nuke:

**Option 1: Python Script in Nuke**
```python
# In Nuke Script Editor
import json

roto_node = nuke.selectedNode()  # Select your Roto node first
curves_data = []

for curve in roto_node['curves']:
    points = []
    for point in curve.points:
        points.append({
            'x': point.center.x,
            'y': point.center.y
        })
    
    curves_data.append({
        'name': curve.name,
        'points': points
    })

print(json.dumps({'curves': curves_data}, indent=2))
# Copy the output and paste into the Mask Editor
```

**Option 2: Copy Node**
1. Select Roto node
2. Ctrl+C (copy)
3. Paste into Mask Editor

#### Coordinate System Handling:
- **Nuke coordinates (0-1)**: Automatically detected and scaled
- **Pixel coordinates**: Automatically normalized
- **Animation keyframes**: Transferred with correct timing

#### What Gets Imported:
✅ Bezier shapes and points  
✅ Shape names  
✅ Position keyframes  
✅ Opacity keyframes (if present)  
✅ Multiple shapes in one import  

#### Limitations:
- Only supports Bezier/Roto shapes (no circle/rectangle)
- Basic animation interpolation (linear)
- No RotoPaint layer compositing modes (yet)

## 📊 Updated UI Elements

### Timeline Sidebar:
```
┌─────────────────────────────────┐
│ Timeline & Keyframes            │
│                                 │
│ ▮ Position/Size/Rotation        │ ← Blue keyframes
│ ▮ Opacity Only                  │ ← Orange keyframes
│                                 │
│ Move shapes at different frames │
│ to create keyframes!            │
├─────────────────────────────────┤
│ All Keyframes (5 frames)        │
│ [Timeline with mixed colors]    │
│                                 │
│ circle (3 keyframes)            │
│ [Blue|Orange|Blue keyframes]    │
└─────────────────────────────────┘
```

### Left Sidebar New Button:
```
┌─────────────────────┐
│ 👁️ Hide Outlines   │
│ 📋 Import from Nuke │ ← NEW!
└─────────────────────┘
```

## 🎯 Use Cases

### Professional Rotoscoping Workflow:
1. **Rough in Nuke**: Create initial roto shapes with Nuke's tools
2. **Import to ComfyUI**: Paste shapes into Mask Editor
3. **Refine**: Use multi-select, bezier editing, and auto-keyframing
4. **Generate Masks**: Create animated masks for inpainting/compositing

### Opacity Animation Workflow:
1. Create shape at frame 0
2. Add position/size keyframes (blue)
3. Add fade in/out with opacity keyframes (orange)
4. Easily see which frames control what

### Cross-Application Pipeline:
```
Nuke Roto → Copy → ComfyUI Mask Drawer → Animated Masks → Inpainting/Effects
```

## 🔧 Technical Implementation

### Opacity-Only Detection:
```javascript
// Compares each keyframe to adjacent keyframes
// If ONLY opacity changed → Orange
// If position/size/rotation changed → Blue

const isOpacityOnly = !positionChanged && 
                      !sizeChanged && 
                      !rotationChanged;
```

### Import Parser:
- Supports JSON, Python dict, and basic TCL
- Auto-detects coordinate systems
- Handles both normalized (0-1) and pixel coordinates
- Preserves animation timing

### Data Persistence:
- JSON format in ComfyUI temp directory
- Includes all shape properties and keyframes
- Loads on editor initialization
- Survives ComfyUI restarts (until temp cleaned)

## ⌨️ Updated Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Ctrl+V** | Auto-detect Nuke data paste |
| **Ctrl+Z** | Undo |
| **Shift+Click** | Multi-select |
| **Delete** | Delete shape/keyframe |

## 🐛 Known Issues & Solutions

**Issue**: Import shows "No valid shapes found"
- **Solution**: Ensure data includes at least 3 points per curve
- Check that data is valid JSON or Python dict format

**Issue**: Imported shapes in wrong position
- **Solution**: Nuke may use different coordinate origin
- Use video dimensions to normalize coordinates

**Issue**: Masks don't load after restart
- **Solution**: Temp directory may be cleared
- For permanent storage, export/import workflow data

## 📝 Example Nuke Import

### Simple Bezier:
```python
{
  'curves': [{
    'name': 'Head_Mask',
    'points': [
      {'x': 0.45, 'y': 0.30},
      {'x': 0.55, 'y': 0.30},
      {'x': 0.60, 'y': 0.50},
      {'x': 0.50, 'y': 0.65},
      {'x': 0.40, 'y': 0.50}
    ]
  }]
}
```

### Animated Bezier:
```python
{
  'curves': [{
    'name': 'Moving_Shape',
    'points': [...],  # Initial points
    'keyframes': [
      {
        'frame': 0,
        'points': [...]  # Points at frame 0
      },
      {
        'frame': 50,
        'points': [...],  # Points at frame 50
        'opacity': 0.5
      }
    ]
  }]
}
```

## 🚀 Quick Start

1. **Draw in Nuke**: Create your roto shapes
2. **Export**: Use the Python script above or copy node
3. **Import**: Paste into Mask Editor (Ctrl+V or button)
4. **Refine**: Use existing tools (multi-select, undo, etc.)
5. **Animate**: Add opacity keyframes (orange)
6. **Save**: Generate masks for ComfyUI

## 💡 Pro Tips

### Tip 1: Combine Nuke + Manual
- Import rough shapes from Nuke
- Add detail shapes manually
- Use multi-select to animate together

### Tip 2: Color-Coded Animation
- Use blue keyframes for motion tracking
- Use orange keyframes for fade effects
- Clean timeline visualization

### Tip 3: Workflow Efficiency
```
Nuke (rough roto) → Import → ComfyUI (refinement) → Masks
```

### Tip 4: Data Persistence
- Masks auto-save between sessions
- No need to manually save/load
- Work across multiple ComfyUI runs

## 📦 Installation

Same as before - replace these files in your ComfyUI custom nodes folder:
1. `animated_mask_editor.html` (updated)
2. `animated_mask_node.py` (unchanged)
3. `animated_mask_drawer.js` (unchanged)

Restart ComfyUI and enjoy the new features!

## 🎬 Version History

**v2.1** (This Update):
- ✅ Orange keyframes for opacity-only changes
- ✅ Persistent mask saving/loading
- ✅ Nuke roto import (Python/JSON/TCL)
- ✅ Auto-paste detection
- ✅ Keyframe color legend

**v2.0** (Previous):
- Multi-select with box selection
- Undo system (Ctrl+Z)
- Fixed bezier dragging
- Unified timeline
- Automatic rotation keyframes

## 📞 Need Help?

Check the import dialog for format examples, or use the Nuke Python script provided above to ensure correct format.

Happy masking! 🎨✨
