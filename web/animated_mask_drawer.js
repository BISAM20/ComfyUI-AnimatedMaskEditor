import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";
import { api } from "../../scripts/api.js";

// Add custom widget to the node
app.registerExtension({
    name: "AnimatedMaskDrawer.LaunchEditor",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "AnimatedMaskDrawer") {

            // Add button to launch editor
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                // Hide the serialized data widget. It still serializes into the
                // workflow (so shapes survive restarts) but is not drawn.
                const dataWidget = this.widgets?.find(w => w.name === "mask_data");
                if (dataWidget) {
                    // Collapse to zero height and no-op the draw so it stays
                    // invisible, but keep its original type so its value still
                    // serializes into the workflow normally.
                    dataWidget.computeSize = () => [0, -4];
                    dataWidget.draw = () => {};
                    dataWidget.hidden = true;
                    if (dataWidget.value == null) dataWidget.value = "";
                    this.maskDataWidget = dataWidget;
                }

                // Add "Launch Editor" button
                const launchBtn = this.addWidget("button", "🎨 Launch Mask Editor", null, () => {
                    openMaskEditor(this);
                });

                return r;
            }
        }
    }
});

// Channel used by the popup editor to hand saved shape data back to the graph.
const maskEditorChannel = new BroadcastChannel("roto_mask_editor");
maskEditorChannel.onmessage = (e) => {
    const { node, data } = e.data || {};
    if (node === undefined || data === undefined) return;

    // Find the node that opened the editor and store the shapes in its hidden
    // widget so they serialize into the workflow (survives restart / travels).
    const graphNode = app.graph?.getNodeById?.(node);
    if (graphNode && graphNode.maskDataWidget) {
        graphNode.maskDataWidget.value = data;
        app.graph.setDirtyCanvas(true, true);
    }
};

// Open mask editor in new window for a specific node instance.
async function openMaskEditor(node) {
    const nodeId = node?.id;

    // Push this node's current shapes to the server so the editor loads exactly
    // what is stored in the workflow (important after a restart / reload).
    if (nodeId !== undefined && node.maskDataWidget) {
        try {
            await api.fetchApi('/animated_mask_editor/stash', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ node: nodeId, data: node.maskDataWidget.value || "" })
            });
        } catch (err) {
            console.warn('[AnimatedMaskDrawer] stash failed:', err);
        }
    }

    const width = 1400;
    const height = 800;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;

    const url = nodeId !== undefined
        ? `/animated_mask_editor?node=${encodeURIComponent(nodeId)}`
        : '/animated_mask_editor';

    const editorWindow = window.open(
        url,
        `MaskEditor_${nodeId}`,
        `width=${width},height=${height},left=${left},top=${top},resizable=yes`
    );

    if (!editorWindow) {
        alert('Please allow pop-ups for this site to use the Mask Editor');
    }
}

// Add custom styling
const style = document.createElement('style');
style.textContent = `
    .comfy-widget button[name="🎨 Launch Mask Editor"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: bold;
        border: none;
        padding: 10px;
        cursor: pointer;
        border-radius: 4px;
        transition: transform 0.2s;
        margin-bottom: 5px;
    }
    
    .comfy-widget button[name="🎨 Launch Mask Editor"]:hover {
        transform: scale(1.05);
    }
`;
document.head.appendChild(style);
