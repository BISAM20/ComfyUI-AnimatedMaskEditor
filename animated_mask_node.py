import torch
import numpy as np
from PIL import Image, ImageDraw
import json
import os
import folder_paths
from server import PromptServer
from aiohttp import web
import base64
import io

# --- Persistent per-node shape storage -------------------------------------
# Disk backup lives next to the node (NOT in ComfyUI's temp dir, which is wiped
# on restart). The widget value stored in the workflow is the primary store;
# these files are the "both" safety net and a fallback for headless runs.
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "roto_data")
DEFAULT_NODE_KEY = "_default"

# In-memory mirror of the latest saved data per node, populated by the editor's
# /save route so /load can serve it without a disk round-trip.
roto_store = {}


def node_key_for(unique_id):
    """Normalize a node id (or missing id) into a safe filesystem/dict key."""
    if unique_id is None or unique_id == "":
        return DEFAULT_NODE_KEY
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(unique_id))


def get_backup_path(node_key):
    """Persistent per-node backup file path."""
    return os.path.join(BACKUP_DIR, f"roto_{node_key}.json")


def parse_mask_data(mask_data):
    """Parse the serialized widget string. Returns dict or None if empty/invalid."""
    if not mask_data or not str(mask_data).strip():
        return None
    try:
        data = json.loads(mask_data)
        if isinstance(data, dict) and "shapes" in data:
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def load_backup(node_key):
    """Load the per-node disk backup. Returns dict or None."""
    path = get_backup_path(node_key)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_backup(node_key, data):
    """Write the per-node disk backup and update the in-memory mirror."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    roto_store[node_key] = data
    with open(get_backup_path(node_key), 'w') as f:
        json.dump(data, f, indent=2)


def resolve_size(value, dim, default):
    """Resolve a shape size (radius/width/height) to output pixels.

    Sizes are stored normalized (0-1, a fraction of the frame) so masks render
    at the correct size for ANY output resolution. Legacy data stored absolute
    pixels (> 1); those are passed through unchanged for backward compatibility.
    """
    if value is None:
        value = default
    return value * dim if value <= 1.0 else value


class AnimatedMaskDrawer:
    """
    ComfyUI Custom Node for drawing animated masks with keyframes
    Includes integrated web UI that launches from the node
    """
    
    # Per-node video store (keyed by node unique_id). Replaces the old single
    # global so multiple Roto nodes don't clobber each other's frames.
    current_videos = {}
    last_video = None  # fallback for calls without a node id
    last_params_hash = None

    def __init__(self):
        self.mask_data = {}

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": ("IMAGE", {"tooltip": "Input video or image batch to create masks for"}),
            },
            "optional": {
                "mask_data": ("STRING", {
                    "default": "",
                    "tooltip": "Serialized roto shapes/keyframes (hidden - managed by the editor). Stored in the workflow so shapes survive restarts."
                }),
                "width": ("INT", {
                    "default": 512, 
                    "min": 64, 
                    "max": 4096,
                    "tooltip": "Output mask width (leave 512 to auto-detect from video)"
                }),
                "height": ("INT", {
                    "default": 512, 
                    "min": 64, 
                    "max": 4096,
                    "tooltip": "Output mask height (leave 512 to auto-detect from video)"
                }),
                "feather": ("INT", {
                    "default": 0, 
                    "min": 0, 
                    "max": 100,
                    "tooltip": "Blur radius for soft edges (10-20 recommended for smooth masks)"
                }),
                "invert": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Invert mask (swap masked/unmasked areas)"
                }),
                "refresh": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 999999,
                    "tooltip": "Increment this value to force regeneration of masks"
                }),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }
    
    RETURN_TYPES = ("MASK", "IMAGE", "IMAGE")
    RETURN_NAMES = ("mask_sequence", "mask_preview", "masked_video")
    OUTPUT_TOOLTIPS = (
        "Animated mask sequence (batch) - Use for inpainting, effects, compositing",
        "Video with red mask overlay - Connect to Preview Image to see masks",
        "Input video with white masks overlaid (100% opacity)"
    )
    FUNCTION = "generate_masks"
    CATEGORY = "mask/animation"
    OUTPUT_NODE = False
    
    def generate_masks(self, video, width=None, height=None, feather=0, invert=False, refresh=0,
                       mask_data="", unique_id=None):
        """
        Generate animated masks based on keyframe data
        """
        # Store video reference per-node for the editor UI to fetch frames.
        node_key = node_key_for(unique_id)
        AnimatedMaskDrawer.current_videos[node_key] = video
        AnimatedMaskDrawer.last_video = video

        print(f"[AnimatedMaskDrawer] Video stored for node {node_key}: {video.shape}")

        # Resolve shape data. Priority:
        #   1. mask_data widget (serialized in the workflow -> survives restarts)
        #   2. per-node disk backup file
        #   3. empty
        data = parse_mask_data(mask_data)
        if data is None:
            data = load_backup(node_key)
        if data is None:
            data = {"shapes": [], "keyframes": {}}
        
        # Get video dimensions
        batch_size = video.shape[0]
        video_height, video_width = video.shape[1], video.shape[2]
        
        # Use video dimensions if width/height not specified or are default
        if width is None or width == 512:
            width = video_width
        if height is None or height == 512:
            height = video_height
        
        masks = []
        preview_frames = []
        masked_video_frames = []
        
        for frame_idx in range(batch_size):
            # Create blank mask - START WITH BLACK (0)
            mask_img = Image.new('L', (width, height), 0)
            draw = ImageDraw.Draw(mask_img)
            
            # Get interpolated shapes for this frame
            frame_shapes = self.interpolate_frame(data, frame_idx, batch_size)
            
            # Draw each shape - shapes will be WHITE on black background
            for shape in frame_shapes:
                self.draw_shape(draw, shape, width, height)
            
            # Convert to tensor
            mask_array = np.array(mask_img).astype(np.float32) / 255.0
            
            # Apply feathering if needed
            if feather > 0:
                mask_array = self.apply_feather(mask_array, feather)
            
            # Invert if needed (AFTER drawing, so default shows drawn areas as white)
            if invert:
                mask_array = 1.0 - mask_array
            
            masks.append(mask_array)
            
            # Create preview frame (video with red mask overlay)
            # Resize mask to match video dimensions if needed
            if mask_array.shape != (video_height, video_width):
                from PIL import Image as PILImage
                mask_pil = PILImage.fromarray((mask_array * 255).astype(np.uint8))
                mask_pil = mask_pil.resize((video_width, video_height), PILImage.LANCZOS)
                mask_array_resized = np.array(mask_pil).astype(np.float32) / 255.0
            else:
                mask_array_resized = mask_array
            
            frame = video[frame_idx].cpu().numpy()
            
            # Red overlay preview
            overlay = frame.copy()
            overlay[:, :, 0] = np.clip(overlay[:, :, 0] + mask_array_resized * 0.4, 0, 1)
            preview_frames.append(overlay)
            
            # White mask overlay on video (100% opacity)
            masked_video = frame.copy()
            # Where mask is active (white), make the video white
            mask_3channel = np.stack([mask_array_resized] * 3, axis=-1)
            masked_video = masked_video * (1 - mask_3channel) + mask_3channel
            masked_video_frames.append(masked_video)
        
        # Stack masks into batch
        mask_tensor = torch.from_numpy(np.stack(masks))
        
        # Stack preview frames
        preview_tensor = torch.from_numpy(np.stack(preview_frames))
        
        # Stack masked video frames
        masked_video_tensor = torch.from_numpy(np.stack(masked_video_frames))
        
        return (mask_tensor, preview_tensor, masked_video_tensor)
    
    def interpolate_frame(self, data, frame_idx, total_frames):
        """
        Interpolate shape properties based on keyframes
        """
        shapes = data.get("shapes", [])
        keyframes = data.get("keyframes", {})
        
        interpolated = []
        
        for shape in shapes:
            shape_id = str(shape.get("id"))
            shape_keyframes = keyframes.get(shape_id, [])
            
            if not shape_keyframes:
                # No keyframes, use default values
                interpolated.append(shape)
                continue
            
            # Find surrounding keyframes
            kf_before = None
            kf_after = None
            
            for kf in sorted(shape_keyframes, key=lambda x: x["frame"]):
                if kf["frame"] <= frame_idx:
                    kf_before = kf
                elif kf["frame"] > frame_idx and kf_after is None:
                    kf_after = kf
            
            # Interpolate properties
            if kf_before and kf_after:
                # Linear interpolation
                progress = (frame_idx - kf_before["frame"]) / (kf_after["frame"] - kf_before["frame"])
                interpolated_shape = self.lerp_shape(shape, kf_before, kf_after, progress)
            elif kf_before:
                interpolated_shape = {**shape, **kf_before.get("properties", {})}
            else:
                interpolated_shape = shape
            
            interpolated.append(interpolated_shape)
        
        return interpolated
    
    def lerp_shape(self, base_shape, kf1, kf2, t):
        """
        Linear interpolation between two keyframes
        """
        result = base_shape.copy()
        props1 = kf1.get("properties", {})
        props2 = kf2.get("properties", {})
        
        # Interpolate numeric properties
        for key in ["x", "y", "width", "height", "radius", "opacity", "rotation"]:
            if key in props1 and key in props2:
                result[key] = props1[key] + (props2[key] - props1[key]) * t
        
        return result
    
    def draw_shape(self, draw, shape, img_width, img_height):
        """
        Draw a shape on the mask with rotation support
        """
        shape_type = shape.get("type", "circle")
        x = shape.get("x", 0.5) * img_width
        y = shape.get("y", 0.5) * img_height
        opacity = int(shape.get("opacity", 1.0) * 255)
        rotation = shape.get("rotation", 0)
        
        if shape_type == "circle":
            # Radius is stored normalized (fraction of width); scale to output px.
            radius = resolve_size(shape.get("radius"), img_width, 50)
            # Create a temporary image for rotation
            if rotation != 0:
                size = int(radius * 2.5)
                temp_img = Image.new('L', (size, size), 0)
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.ellipse([size//2 - radius, size//2 - radius,
                                  size//2 + radius, size//2 + radius], fill=opacity)
                temp_img = temp_img.rotate(rotation, expand=False)
                # Paste the rotated image
                paste_x = int(x - size // 2)
                paste_y = int(y - size // 2)
                draw._image.paste(temp_img, (paste_x, paste_y), temp_img)
            else:
                draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=opacity)

        elif shape_type == "rectangle":
            # Width/height stored normalized (fraction of each dim); scale to px.
            w = resolve_size(shape.get("width"), img_width, 100)
            h = resolve_size(shape.get("height"), img_height, 100)

            if rotation != 0:
                # Create temporary image for rotation
                size = int(max(w, h) * 1.5)
                temp_img = Image.new('L', (size, size), 0)
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.rectangle([size//2 - w//2, size//2 - h//2, 
                                    size//2 + w//2, size//2 + h//2], fill=opacity)
                temp_img = temp_img.rotate(rotation, expand=False)
                paste_x = int(x - size // 2)
                paste_y = int(y - size // 2)
                draw._image.paste(temp_img, (paste_x, paste_y), temp_img)
            else:
                draw.rectangle([x - w/2, y - h/2, x + w/2, y + h/2], fill=opacity)
        
        elif shape_type == "bezier" or shape_type == "polygon":
            points = shape.get("points", [])
            if points:
                # Handle both dict and tuple formats
                if isinstance(points[0], dict):
                    scaled_points = [(p['x'] * img_width, p['y'] * img_height) for p in points]
                else:
                    scaled_points = [(p[0] * img_width, p[1] * img_height) for p in points]
                
                if len(scaled_points) >= 3:
                    if rotation != 0:
                        # Rotate points around center
                        cx = x
                        cy = y
                        rot_rad = np.radians(rotation)
                        cos_r = np.cos(rot_rad)
                        sin_r = np.sin(rot_rad)
                        
                        rotated_points = []
                        for px, py in scaled_points:
                            # Translate to origin
                            px -= cx
                            py -= cy
                            # Rotate
                            new_x = px * cos_r - py * sin_r
                            new_y = px * sin_r + py * cos_r
                            # Translate back
                            rotated_points.append((new_x + cx, new_y + cy))
                        
                        draw.polygon(rotated_points, fill=opacity)
                    else:
                        draw.polygon(scaled_points, fill=opacity)
    
    def apply_feather(self, mask, feather_radius):
        """
        Apply Gaussian blur for feathering effect
        """
        try:
            from scipy.ndimage import gaussian_filter
            return gaussian_filter(mask, sigma=feather_radius/3)
        except:
            return mask


# Web server routes for the integrated UI
@PromptServer.instance.routes.get("/animated_mask_editor")
async def get_editor(request):
    """Serve the mask editor UI"""
    html_path = os.path.join(os.path.dirname(__file__), "animated_mask_editor.html")
    
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    else:
        # Fallback: serve embedded HTML
        html_content = get_embedded_html()
    
    return web.Response(text=html_content, content_type='text/html')

def _request_node_key(request):
    """Resolve the per-node storage key from the ?node= query param."""
    return node_key_for(request.query.get('node'))


def _get_node_video(node_key):
    """Return the stored video tensor for a node, falling back to the last seen."""
    video = AnimatedMaskDrawer.current_videos.get(node_key)
    if video is None:
        video = AnimatedMaskDrawer.last_video
    return video


@PromptServer.instance.routes.post("/animated_mask_editor/save")
async def save_mask_data(request):
    """Save mask data from the editor to this node's persistent backup."""
    node_key = _request_node_key(request)
    data = await request.json()

    save_backup(node_key, data)

    return web.json_response({"success": True, "node": node_key, "path": get_backup_path(node_key)})

@PromptServer.instance.routes.post("/animated_mask_editor/stash")
async def stash_mask_data(request):
    """Receive the node's current widget value (from the JS extension) so the
    editor can load exactly what's stored in the workflow, even after a restart."""
    body = await request.json()
    node_key = node_key_for(body.get('node'))
    parsed = parse_mask_data(body.get('data'))
    if parsed is not None:
        roto_store[node_key] = parsed
    return web.json_response({"success": True, "node": node_key})

@PromptServer.instance.routes.get("/animated_mask_editor/load")
async def load_mask_data(request):
    """Load existing mask data for a node (in-memory mirror, else disk backup)."""
    node_key = _request_node_key(request)
    data = roto_store.get(node_key)
    if data is None:
        data = load_backup(node_key)
    if data is None:
        data = {"shapes": [], "keyframes": {}}
    return web.json_response(data)

@PromptServer.instance.routes.get("/animated_mask_editor/video_info")
async def get_video_info(request):
    """Get video information (frame count, dimensions) for a node."""
    try:
        node_key = _request_node_key(request)
        video = _get_node_video(node_key)

        if video is not None:
            info = {
                "total_frames": int(video.shape[0]),
                "width": int(video.shape[2]),
                "height": int(video.shape[1]),
                "has_video": True
            }
            print(f"[AnimatedMaskDrawer] video_info for node {node_key}: {info}")
            return web.json_response(info)
        else:
            print(f"[AnimatedMaskDrawer] No video for node {node_key} - queue the workflow first")
            return web.json_response({"has_video": False, "error": "No video loaded. Please queue the workflow in ComfyUI first."})
    except Exception as e:
        print(f"[AnimatedMaskDrawer] Error getting video info: {e}")
        import traceback
        traceback.print_exc()
        return web.json_response({"has_video": False, "error": str(e)})

@PromptServer.instance.routes.get("/animated_mask_editor/video_frame")
async def get_video_frame(request):
    """Get specific video frame as base64 JPEG for a node."""
    frame_idx = int(request.query.get('frame', 0))
    node_key = _request_node_key(request)

    video = _get_node_video(node_key)
    if video is None:
        return web.json_response({"error": "No video loaded"})

    # Clamp frame index
    frame_idx = max(0, min(frame_idx, video.shape[0] - 1))
    
    # Get frame (tensor to numpy)
    frame = video[frame_idx].cpu().numpy()
    
    # Convert to PIL Image (0-1 float to 0-255 uint8)
    frame_uint8 = (frame * 255).astype(np.uint8)
    img = Image.fromarray(frame_uint8)
    
    # Convert to JPEG base64
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return web.json_response({
        "frame": frame_idx,
        "image": f"data:image/jpeg;base64,{img_base64}"
    })


def get_embedded_html():
    """Returns embedded HTML if external file not found"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Animated Mask Editor</title>
        <style>
            body {
                margin: 0;
                padding: 20px;
                font-family: Arial, sans-serif;
                background: #1a1a1a;
                color: white;
            }
            h1 { text-align: center; }
            .info {
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background: #2a2a2a;
                border-radius: 8px;
            }
        </style>
    </head>
    <body>
        <h1>Animated Mask Editor</h1>
        <div class="info">
            <p>Please place the animated_mask_editor.html file in the same directory as this node.</p>
            <p>The editor UI will load here once the file is available.</p>
        </div>
    </body>
    </html>
    """


# Node registration for ComfyUI
NODE_CLASS_MAPPINGS = {
    "AnimatedMaskDrawer": AnimatedMaskDrawer
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AnimatedMaskDrawer": "Animated Mask Drawer 🎨"
}

# Add web directory for serving static files
WEB_DIRECTORY = "./web"
