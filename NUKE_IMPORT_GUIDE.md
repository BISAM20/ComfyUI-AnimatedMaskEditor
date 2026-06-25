# 📋 Nuke to ComfyUI - Quick Import Guide

## 🎯 Fastest Method: Copy & Paste

### In Nuke:
1. Select your Roto node
2. Press **Ctrl+C** (or Cmd+C on Mac)

### In ComfyUI Mask Editor:
3. Press **Ctrl+V** (or Cmd+V on Mac)
4. Import dialog opens automatically!
5. Click **"✓ Import"**

Done! Your Nuke roto shapes are now in ComfyUI.

---

## 🐍 Python Script Method (Recommended for Complex Roto)

### Step 1: Run this in Nuke Script Editor

```python
import json

# Make sure your Roto node is selected
roto_node = nuke.selectedNode()

curves_data = []
for curve in roto_node['curves'].getValue():
    # Get curve name
    curve_name = curve.name
    
    # Extract points for current frame
    points = []
    for i in range(curve.getControlPointKeyTimes()[0].getNumKeys()):
        cp = curve.getControlPointKeyTimes()[i]
        center = curve.getControlPointKeyFrames()[i].getPosition()
        points.append({
            'x': center.x / roto_node.width(),  # Normalize to 0-1
            'y': center.y / roto_node.height()
        })
    
    # Get animation keyframes if they exist
    keyframes = []
    for frame in range(int(roto_node.firstFrame()), int(roto_node.lastFrame()) + 1):
        frame_points = []
        for i in range(len(points)):
            cp = curve.getControlPointKeyFrames()[i]
            pos = cp.getPosition(frame)
            frame_points.append({
                'x': pos.x / roto_node.width(),
                'y': pos.y / roto_node.height()
            })
        
        # Only add keyframe if points changed from previous
        if not keyframes or frame_points != keyframes[-1]['points']:
            keyframes.append({
                'frame': frame,
                'points': frame_points
            })
    
    curves_data.append({
        'name': curve_name,
        'points': points,
        'keyframes': keyframes if len(keyframes) > 1 else []
    })

output = json.dumps({'curves': curves_data}, indent=2)
print(output)

# Save to clipboard (requires pyperclip - pip install pyperclip)
try:
    import pyperclip
    pyperclip.copy(output)
    nuke.message("Roto data copied to clipboard! Paste into ComfyUI.")
except:
    nuke.message("Copy the text from the Script Editor and paste into ComfyUI.")
```

### Step 2: Copy Output
- If pyperclip is installed: Data is already in clipboard
- Otherwise: Select and copy the JSON output from Script Editor

### Step 3: Import to ComfyUI
- In Mask Editor, click **"📋 Import from Nuke"**
- Paste the JSON
- Click **"✓ Import"**

---

## 📐 Simple Format Examples

### Single Shape (No Animation):
```python
{
  'curves': [{
    'name': 'Face_Mask',
    'points': [
      {'x': 0.4, 'y': 0.3},
      {'x': 0.6, 'y': 0.3},
      {'x': 0.7, 'y': 0.5},
      {'x': 0.5, 'y': 0.7},
      {'x': 0.3, 'y': 0.5}
    ]
  }]
}
```

### Animated Shape:
```python
{
  'curves': [{
    'name': 'Moving_Head',
    'points': [
      {'x': 0.5, 'y': 0.5},
      {'x': 0.6, 'y': 0.5},
      {'x': 0.6, 'y': 0.6},
      {'x': 0.5, 'y': 0.6}
    ],
    'keyframes': [
      {
        'frame': 0,
        'points': [
          {'x': 0.4, 'y': 0.4},
          {'x': 0.5, 'y': 0.4},
          {'x': 0.5, 'y': 0.5},
          {'x': 0.4, 'y': 0.5}
        ]
      },
      {
        'frame': 50,
        'points': [
          {'x': 0.6, 'y': 0.6},
          {'x': 0.7, 'y': 0.6},
          {'x': 0.7, 'y': 0.7},
          {'x': 0.6, 'y': 0.7}
        ]
      }
    ]
  }]
}
```

### Multiple Shapes:
```python
{
  'curves': [
    {
      'name': 'Shape_1',
      'points': [...]
    },
    {
      'name': 'Shape_2', 
      'points': [...]
    },
    {
      'name': 'Shape_3',
      'points': [...]
    }
  ]
}
```

---

## 🔄 Coordinate Systems

### Nuke Uses:
- **Pixel coordinates**: (0, 0) to (width, height)
- **Or normalized**: (0, 0) to (1, 1)

### Auto-Detection:
The importer automatically detects which system:
- If values > 2: Treats as pixels, divides by video dimensions
- If values ≤ 2: Treats as normalized (0-1)

### Manual Normalization:
If your coordinates are in pixels:
```python
normalized_x = pixel_x / video_width
normalized_y = pixel_y / video_height
```

---

## ⚠️ Common Issues

### "No valid shapes found"
**Cause**: Not enough points
**Fix**: Each curve needs at least 3 points

### "Could not parse data format"
**Cause**: Invalid JSON/Python syntax
**Fix**: 
- Check quotes (use `"` for JSON, `'` for Python)
- Validate JSON at jsonlint.com
- Ensure proper brackets `{}` and `[]`

### Shapes in wrong position
**Cause**: Coordinate system mismatch
**Fix**: 
- Ensure coordinates are 0-1 (normalized)
- Or set values >2 for auto pixel conversion

### Animation not working
**Cause**: Missing keyframes array
**Fix**: Include `'keyframes': [...]` in curve data

---

## 📊 Supported Data Structures

### ✅ Supported:
- JSON format
- Python dictionary format  
- Bezier/polygon shapes
- Static shapes
- Animated shapes with keyframes
- Multiple shapes in one import
- Shape names
- Opacity keyframes

### ❌ Not Yet Supported:
- RotoPaint layers
- Blur/edge feathering from Nuke
- Curve tangent handles
- Layer blend modes
- Tracker data

---

## 💡 Pro Workflow

### 1. Rough Roto in Nuke
- Use Nuke's powerful roto tools
- Create basic shapes and animation
- Don't worry about perfection

### 2. Export Clean Data
- Use the Python script above
- Or just copy the Roto node

### 3. Import to ComfyUI
- Paste with Ctrl+V
- Shapes transfer automatically

### 4. Refine in ComfyUI
- Use multi-select tools
- Add opacity keyframes (orange)
- Position keyframes (blue)
- Undo/redo as needed

### 5. Generate Masks
- Save to ComfyUI
- Use for inpainting, effects, compositing

---

## 🎨 Visual Format Guide

```
Nuke Roto Node Structure:
┌─────────────────────────┐
│ Roto1                   │
│ ├─ Bezier1              │ ← Gets imported as shape
│ │  ├─ Point 1           │
│ │  ├─ Point 2           │
│ │  └─ Point 3           │
│ └─ Bezier2              │ ← Gets imported as shape
│    ├─ Point 1           │
│    └─ Point 2           │
└─────────────────────────┘
                ↓ Export
{
  'curves': [
    {                       ← Bezier1
      'name': 'Bezier1',
      'points': [...]
    },
    {                       ← Bezier2  
      'name': 'Bezier2',
      'points': [...]
    }
  ]
}
                ↓ Import
ComfyUI Shapes:
• Bezier1 (3 keyframes)
• Bezier2 (2 keyframes)
```

---

## 🚀 Quick Reference Table

| Task | Steps |
|------|-------|
| **Import simple shape** | Copy Nuke node → Paste in editor → Import |
| **Import with animation** | Use Python script → Copy JSON → Paste → Import |
| **Multiple shapes** | Select all roto nodes → Export together |
| **Check import** | Look for "Imported X shape(s)" message |
| **Fix bad import** | Ctrl+Z to undo → Fix data → Try again |

---

## 🎯 Success Checklist

Before importing, ensure your data has:
- [ ] Valid JSON or Python dict format
- [ ] At least one curve in 'curves' array
- [ ] At least 3 points per curve
- [ ] Points in format: `{'x': value, 'y': value}`
- [ ] Coordinates normalized (0-1) or pixel values
- [ ] Optional: keyframes with frame numbers

After importing, verify:
- [ ] Shapes appear in shape list
- [ ] Positions look correct
- [ ] Animation keyframes transferred
- [ ] Shape names preserved

---

## 📞 Still Stuck?

1. Start with the simplest example:
```python
{'curves': [{'name': 'Test', 'points': [
  {'x': 0.3, 'y': 0.3},
  {'x': 0.7, 'y': 0.3},
  {'x': 0.5, 'y': 0.7}
]}]}
```

2. Click Import from Nuke button
3. Paste the simple example
4. If that works, add your real data gradually

Happy importing! 🎬✨
