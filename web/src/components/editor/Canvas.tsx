import { useEffect, useRef } from "react";
import { Stage, Layer as KonvaLayer, Rect, Text, Group, Transformer } from "react-konva";
import type Konva from "konva";
import { useEditorStore } from "@/hooks/useEditor";
import type {
  AspectRatio,
  LayerConfigText,
  LayerConfigImage,
  LayerConfigShape,
  LayerConfigProduct,
  TemplateLayer,
} from "@/lib/types";

const ASPECT_DIMENSIONS: Record<AspectRatio, { width: number; height: number }> = {
  "1:1": { width: 540, height: 540 },
  "4:5": { width: 540, height: 675 },
  "9:16": { width: 540, height: 960 },
  "16:9": { width: 720, height: 405 },
};

type Props = {
  showSafeZones: boolean;
  backgroundColor?: string;
};

export function EditorCanvas({ showSafeZones, backgroundColor = "#f5f5f4" }: Props) {
  const layers = useEditorStore((s) => s.layers);
  const template = useEditorStore((s) => s.template);
  const aspectRatio = useEditorStore((s) => s.aspectRatio);
  const selection = useEditorStore((s) => s.selection);
  const selectLayer = useEditorStore((s) => s.selectLayer);
  const selectCanvas = useEditorStore((s) => s.selectCanvas);
  const moveLayer = useEditorStore((s) => s.moveLayer);
  const resizeLayer = useEditorStore((s) => s.resizeLayer);
  const rotateLayer = useEditorStore((s) => s.rotateLayer);

  const dims = ASPECT_DIMENSIONS[aspectRatio];
  const safeZones = template?.safe_zones ?? {};

  const transformerRef = useRef<Konva.Transformer | null>(null);
  const selectedNodeRef = useRef<Konva.Node | null>(null);

  useEffect(() => {
    const tr = transformerRef.current;
    if (!tr) return;
    const stage = tr.getStage();
    if (!stage) return;
    if (selection?.kind === "layer") {
      const node = stage.findOne(`#layer-${selection.id}`);
      selectedNodeRef.current = node ?? null;
      tr.nodes(node ? [node] : []);
    } else {
      selectedNodeRef.current = null;
      tr.nodes([]);
    }
    tr.getLayer()?.batchDraw();
  }, [selection, layers]);

  return (
    <div className="flex flex-1 items-center justify-center overflow-auto bg-stone-100 p-6">
      <div
        className="rounded shadow-md"
        style={{ width: dims.width, height: dims.height, backgroundColor }}
        onClick={(e) => {
          if (e.target === e.currentTarget) selectCanvas();
        }}
      >
        <Stage
          width={dims.width}
          height={dims.height}
          onClick={(e) => {
            if (e.target === e.target.getStage()) selectCanvas();
          }}
        >
          <KonvaLayer>
            <Rect
              x={0}
              y={0}
              width={dims.width}
              height={dims.height}
              fill={backgroundColor}
              listening={false}
            />
            {showSafeZones && (
              <SafeZoneOverlay
                width={dims.width}
                height={dims.height}
                zones={safeZones}
              />
            )}
          </KonvaLayer>

          {layers.map((layer) => (
            <KonvaLayer
              key={layer.id}
              listening={!layer.locked}
              opacity={layer.opacity ?? 1}
              globalCompositeOperation={
                blendToComposite(layer.blend_mode) ?? "source-over"
              }
            >
              <LayerNode
                layer={layer}
                canvasWidth={dims.width}
                canvasHeight={dims.height}
                isSelected={
                  selection?.kind === "layer" && selection.id === layer.id
                }
                onSelect={() => selectLayer(layer.id)}
                onDragEnd={(x, y) => moveLayer(layer.id, x, y)}
                onTransformEnd={(attrs) => {
                  resizeLayer(layer.id, attrs);
                  if (attrs.rotation !== undefined)
                    rotateLayer(layer.id, attrs.rotation);
                }}
              />
            </KonvaLayer>
          ))}

          <KonvaLayer>
            <Transformer
              ref={transformerRef}
              rotateEnabled
              keepRatio={false}
              borderStroke="#0ea5e9"
              anchorStroke="#0ea5e9"
              anchorFill="#fff"
              anchorSize={8}
              boundBoxFunc={(_oldBox, newBox) => {
                if (newBox.width < 10 || newBox.height < 10) return _oldBox;
                return newBox;
              }}
            />
          </KonvaLayer>
        </Stage>
      </div>
    </div>
  );
}

type LayerNodeProps = {
  layer: TemplateLayer;
  canvasWidth: number;
  canvasHeight: number;
  isSelected: boolean;
  onSelect: () => void;
  onDragEnd: (x: number, y: number) => void;
  onTransformEnd: (attrs: {
    x: number;
    y: number;
    width: number;
    height: number;
    rotation: number;
  }) => void;
};

function LayerNode({
  layer,
  canvasWidth,
  canvasHeight,
  isSelected,
  onSelect,
  onDragEnd,
  onTransformEnd,
}: LayerNodeProps) {
  const width =
    layer.width !== undefined
      ? (layer.width / 100) * canvasWidth
      : canvasWidth * 0.6;
  const height =
    layer.height !== undefined
      ? (layer.height / 100) * canvasHeight
      : canvasHeight * 0.2;
  const x = layer.x !== undefined ? (layer.x / 100) * canvasWidth : 10;
  const y = layer.y !== undefined ? (layer.y / 100) * canvasHeight : 10;

  const groupProps = {
    id: `layer-${layer.id}`,
    x,
    y,
    width,
    height,
    rotation: layer.rotation ?? 0,
    draggable: !layer.locked,
    visible: layer.visible !== false,
    onClick: onSelect,
    onTap: onSelect,
    onDragEnd: (e: Konva.KonvaEventObject<DragEvent>) => {
      const node = e.target;
      const nx = (node.x() / canvasWidth) * 100;
      const ny = (node.y() / canvasHeight) * 100;
      onDragEnd(nx, ny);
    },
    onTransformEnd: (e: Konva.KonvaEventObject<Event>) => {
      const node = e.target;
      const scaleX = node.scaleX();
      const scaleY = node.scaleY();
      node.scaleX(1);
      node.scaleY(1);
      const nx = (node.x() / canvasWidth) * 100;
      const ny = (node.y() / canvasHeight) * 100;
      const nw = (width * scaleX / canvasWidth) * 100;
      const nh = (height * scaleY / canvasHeight) * 100;
      onTransformEnd({
        x: nx,
        y: ny,
        width: nw,
        height: nh,
        rotation: node.rotation(),
      });
    },
  };

  return (
    <Group {...groupProps}>
      {renderLayerContent(layer, width, height, isSelected)}
    </Group>
  );
}

function renderLayerContent(
  layer: TemplateLayer,
  width: number,
  height: number,
  isSelected: boolean,
) {
  switch (layer.type) {
    case "text": {
      const cfg = layer.config as LayerConfigText;
      return (
        <Group>
          {cfg.background_color && (
            <Rect
              width={width}
              height={height}
              fill={cfg.background_color}
              cornerRadius={cfg.border_radius ?? 0}
            />
          )}
          <Text
            width={width}
            height={height}
            text={cfg.content ?? ""}
            fontSize={cfg.font_size ?? Math.max(16, width / 10)}
            fontFamily={cfg.font_family ?? "sans-serif"}
            fill={cfg.color ?? "#111"}
            align={cfg.text_align ?? "left"}
            verticalAlign="middle"
            fontStyle={
              cfg.font_weight === "bold"
                ? "bold"
                : cfg.font_weight === "light"
                  ? "300"
                  : "normal"
            }
            shadowColor={cfg.text_shadow?.color}
            shadowBlur={cfg.text_shadow?.blur}
            shadowOffsetX={cfg.text_shadow?.offset_x}
            shadowOffsetY={cfg.text_shadow?.offset_y}
          />
          {isSelected && <Rect width={width} height={height} stroke="#0ea5e9" dash={[4, 4]} strokeWidth={1} listening={false} />}
        </Group>
      );
    }

    case "image": {
      const cfg = layer.config as LayerConfigImage;
      return (
        <Rect
          width={width}
          height={height}
          fill="#d6d3d1"
          cornerRadius={cfg.border_radius ?? 0}
          stroke={cfg.border_color}
          strokeWidth={cfg.border_width ?? 0}
        />
      );
    }

    case "shape": {
      const cfg = layer.config as LayerConfigShape;
      if (cfg.shape_type === "circle") {
        return (
          <Rect
            width={width}
            height={height}
            cornerRadius={Math.min(width, height) / 2}
            fill={cfg.fill_color ?? "#000"}
            stroke={cfg.stroke_color}
            strokeWidth={cfg.stroke_width ?? 0}
          />
        );
      }
      return (
        <Rect
          width={width}
          height={height}
          fill={cfg.fill_color ?? "#000"}
          stroke={cfg.stroke_color}
          strokeWidth={cfg.stroke_width ?? 0}
        />
      );
    }

    case "product_cutout": {
      const cfg = layer.config as LayerConfigProduct;
      return (
        <Group>
          {cfg.shadow !== false && (
            <Rect
              x={cfg.shadow_offset_x ?? 0}
              y={(cfg.shadow_offset_y ?? 8)}
              width={width}
              height={height}
              fill={cfg.shadow_color ?? "rgba(0,0,0,0.35)"}
              cornerRadius={Math.min(width, height) / 4}
              blurRadius={cfg.shadow_blur ?? 16}
              listening={false}
            />
          )}
          <Rect
            width={width}
            height={height}
            fill="#e7e5e4"
            stroke={isSelected ? "#0ea5e9" : undefined}
            dash={isSelected ? [4, 4] : undefined}
          />
        </Group>
      );
    }

    case "ai_background":
    case "ai_image":
    case "video_background":
      return (
        <Rect
          width={width}
          height={height}
          fill="#fef3c7"
          stroke={isSelected ? "#0ea5e9" : undefined}
          dash={isSelected ? [4, 4] : undefined}
        />
      );

    default:
      return (
        <Rect
          width={width}
          height={height}
          fill="#f5f5f4"
          stroke={isSelected ? "#0ea5e9" : undefined}
          dash={isSelected ? [4, 4] : undefined}
        />
      );
  }
}

function SafeZoneOverlay({
  width,
  height,
  zones,
}: {
  width: number;
  height: number;
  zones: {
    top?: number;
    bottom?: number;
    left?: number;
    right?: number;
  };
}) {
  return (
    <Group listening={false}>
      {zones.top !== undefined && (
        <Rect x={0} y={0} width={width} height={(zones.top / 100) * height} fill="rgba(239,68,68,0.12)" />
      )}
      {zones.bottom !== undefined && (
        <Rect
          x={0}
          y={height - (zones.bottom / 100) * height}
          width={width}
          height={(zones.bottom / 100) * height}
          fill="rgba(239,68,68,0.12)"
        />
      )}
      {zones.left !== undefined && (
        <Rect x={0} y={0} width={(zones.left / 100) * width} height={height} fill="rgba(239,68,68,0.08)" />
      )}
      {zones.right !== undefined && (
        <Rect
          x={width - (zones.right / 100) * width}
          y={0}
          width={(zones.right / 100) * width}
          height={height}
          fill="rgba(239,68,68,0.08)"
        />
      )}
    </Group>
  );
}

function blendToComposite(
  blend?: TemplateLayer["blend_mode"],
): GlobalCompositeOperation | null {
  switch (blend) {
    case "multiply":
      return "multiply";
    case "screen":
      return "screen";
    case "overlay":
      return "overlay";
    case "soft_light":
      return "soft-light";
    default:
      return null;
  }
}