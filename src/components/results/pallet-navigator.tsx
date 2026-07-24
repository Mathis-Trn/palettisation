import type { PalletResult } from "@/domain/types";
import { Button } from "@/components/ui/button";
import { formatPercent } from "@/lib/format";

export function PalletNavigator({
  pallets,
  selectedIndex,
  onSelect,
}: {
  pallets: PalletResult[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {pallets.map((pallet) => (
        <Button
          key={pallet.index}
          size="sm"
          variant={selectedIndex === pallet.index ? "turquoise" : "secondary"}
          onClick={() => onSelect(pallet.index)}
        >
          Palette {pallet.index + 1}
          <span className="ml-1 text-xs opacity-80">({formatPercent(pallet.volumeUsageRatio)})</span>
        </Button>
      ))}
    </div>
  );
}
