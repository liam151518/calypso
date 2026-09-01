"""app/node_schema.py. JSON Schema definitions for every pipeline node.

The Phase A pipeline builder exposes a schema-driven inspector (see
`web/src/components/pipeline/Inspector.tsx`) that renders the right form
based on each node type's JSON Schema. This module is the single source of
truth for those schemas, and also mirrors the inputs that
`app/pipeline_nodes.py` consumes when executing a node.

Adding a new node type? Add an entry below, register the runner in
`pipeline_nodes.NODE_RUNNERS`, and the SPA inspector picks it up.

Schema conventions:
- `properties.params` holds the user-editable params.
- `properties.outputs` declares the typed outputs the node produces
  (used by the executor when wiring edges).
"""

from __future__ import annotations

from typing import Any

# A JSON Schema fragment for the pipeline executable layer.
NODE_SCHEMAS: dict[str, dict[str, Any]] = {
    "trigger": {
        "title": "Trigger",
        "category": "control",
        "description": "Start the run. Exactly one Trigger per pipeline.",
        "outputs": ["flow"],
        "params": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["manual", "schedule", "webhook"],
                    "default": "manual",
                    "title": "Mode",
                },
                "cron": {
                    "type": "string",
                    "title": "Cron expression (when mode = schedule)",
                    "description": "Standard 5-field cron, e.g. '0 9 * * 1'.",
                },
            },
            "required": ["mode"],
        },
    },
    "brand": {
        "title": "Brand",
        "category": "input",
        "description": "Pull the active brand (or a named brand) into the run.",
        "inputs": ["flow"],
        "outputs": ["brand"],
        "params": {
            "type": "object",
            "properties": {
                "brand_id": {
                    "type": "integer",
                    "title": "Brand id",
                    "description": "Leave 0 for the currently active brand.",
                    "default": 0,
                },
            },
        },
    },
    "reference": {
        "title": "Reference",
        "category": "input",
        "description": "Pick references by id or by tag.",
        "inputs": ["flow"],
        "outputs": ["refs"],
        "params": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["ids", "tag"],
                    "default": "tag",
                    "title": "Pick by",
                },
                "tag": {"type": "string", "title": "Tag (when mode = tag)"},
                "ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "title": "Reference ids (when mode = ids)",
                },
                "limit": {"type": "integer", "title": "Max references", "default": 8},
            },
            "required": ["mode"],
        },
    },
    "prompt": {
        "title": "Prompt",
        "category": "input",
        "description": "Pick a prompt draft or write inline text.",
        "inputs": ["flow"],
        "outputs": ["prompt"],
        "params": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["draft", "inline"],
                    "default": "draft",
                    "title": "Source",
                },
                "draft_id": {"type": "integer", "title": "Draft id (when mode = draft)"},
                "body": {
                    "type": "string",
                    "title": "Inline prompt text (when mode = inline)",
                },
                "category": {"type": "string", "title": "Tag category for new drafts"},
            },
            "required": ["mode"],
        },
    },
    "model": {
        "title": "Model",
        "category": "input",
        "description": "Pick which fal.ai model to use.",
        "inputs": ["flow"],
        "outputs": ["model"],
        "params": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "title": "Model id",
                    "default": "minimax/h3",
                },
            },
            "required": ["model_id"],
        },
    },
    "cost_guard": {
        "title": "Cost Guard",
        "category": "control",
        "description": "Stop the run if estimated cost exceeds cap.",
        "inputs": ["flow", "cost_estimate"],
        "outputs": ["flow"],
        "params": {
            "type": "object",
            "properties": {
                "max_usd": {
                    "type": "number",
                    "title": "Max USD",
                    "default": 5.0,
                    "minimum": 0,
                },
            },
            "required": ["max_usd"],
        },
    },
    "generate": {
        "title": "Generate (video)",
        "category": "action",
        "description": "Generate a video job via the existing jobs.py executor.",
        "inputs": ["flow", "prompt", "model", "refs", "brand"],
        "outputs": ["video_job"],
        "params": {
            "type": "object",
            "properties": {
                "duration": {
                    "type": "integer",
                    "enum": [4, 6, 8, 10, 12],
                    "default": 8,
                    "title": "Duration (s)",
                },
                "resolution": {
                    "type": "string",
                    "enum": ["480p", "768p", "1080p"],
                    "default": "768p",
                },
            },
        },
    },
    "image": {
        "title": "Image",
        "category": "action",
        "description": "Generate an image job via the existing image_jobs.py executor.",
        "inputs": ["flow", "prompt", "model", "ref_ids", "brand"],
        "outputs": ["image_job"],
        "params": {
            "type": "object",
            "properties": {
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
                    "default": "1:1",
                },
                "num_images": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 4,
                    "default": 1,
                },
            },
        },
    },
    "combine": {
        "title": "Combine",
        "category": "action",
        "description": "Concatenate / crossfade outputs from upstream nodes.",
        "inputs": ["flow", "video_job"],
        "outputs": ["combined"],
        "params": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["concat", "crossfade"],
                    "default": "concat",
                    "title": "Mode",
                },
                "crossfade_ms": {
                    "type": "integer",
                    "default": 250,
                    "title": "Crossfade (ms, mode = crossfade)",
                },
            },
            "required": ["mode"],
        },
    },
    "export": {
        "title": "Export",
        "category": "action",
        "description": "Persist outputs to /outputs/ and emit a webhook.",
        "inputs": ["flow", "video_job", "image_job", "combined"],
        "outputs": ["exported_url"],
        "params": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "enum": ["outputs", "webhook"],
                    "default": "outputs",
                },
                "webhook_url": {"type": "string", "title": "Webhook URL"},
            },
            "required": ["destination"],
        },
    },
}


def schema_for(node_type: str) -> dict[str, Any] | None:
    """Return the JSON Schema for a node type, or None if unknown."""
    return NODE_SCHEMAS.get(node_type)


def all_schemas() -> dict[str, dict[str, Any]]:
    """Return every schema. Used by the SPA to render the node palette."""
    return NODE_SCHEMAS


def node_categories() -> dict[str, list[str]]:
    """Group node types by category for the palette's sections."""
    out: dict[str, list[str]] = {}
    for node_type, schema in NODE_SCHEMAS.items():
        out.setdefault(schema.get("category", "other"), []).append(node_type)
    return out
