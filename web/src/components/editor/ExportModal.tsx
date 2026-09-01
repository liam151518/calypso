import { useState } from "react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = {
  open: boolean;
  onClose: () => void;
  onConfirm: (opts: { format: "png" | "jpeg"; quality: number; burnCaption: boolean; filename: string }) => void;
  exporting?: boolean;
};

export function ExportModal({ open, onClose, onConfirm, exporting }: Props) {
  const [format, setFormat] = useState<"png" | "jpeg">("png");
  const [quality, setQuality] = useState(0.92);
  const [burnCaption, setBurnCaption] = useState(false);
  const [filename, setFilename] = useState("export.png");

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Export image</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-3 items-center gap-2">
            <Label>Format</Label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value as "png" | "jpeg")}
              className="col-span-2 h-8 rounded border px-2 text-sm"
            >
              <option value="png">PNG</option>
              <option value="jpeg">JPEG</option>
            </select>
          </div>
          <div className="grid grid-cols-3 items-center gap-2">
            <Label>Quality</Label>
            <Input
              type="number"
              min={0.1}
              max={1}
              step={0.05}
              value={quality}
              onChange={(e) => setQuality(parseFloat(e.target.value))}
              className="col-span-2 h-8"
              disabled={format === "png"}
            />
          </div>
          <div className="grid grid-cols-3 items-center gap-2">
            <Label>Burn caption</Label>
            <input
              type="checkbox"
              checked={burnCaption}
              onChange={(e) => setBurnCaption(e.target.checked)}
              className="col-span-2"
            />
          </div>
          <div className="grid grid-cols-3 items-center gap-2">
            <Label>Filename</Label>
            <Input
              value={filename}
              onChange={(e) => setFilename(e.target.value)}
              className="col-span-2 h-8"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => onConfirm({ format, quality, burnCaption, filename })}
            disabled={exporting}
          >
            {exporting ? "Exporting…" : "Export"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}