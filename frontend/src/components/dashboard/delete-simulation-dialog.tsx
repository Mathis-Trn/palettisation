"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";

export function DeleteSimulationDialog({ name, onConfirm }: { name: string; onConfirm: () => void }) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={`Supprimer ${name}`}>
          <Trash2 className="h-4 w-4 text-danger-500" />
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Supprimer la simulation ?</DialogTitle>
        <DialogDescription>
          « {name} » sera définitivement supprimée du stockage local de ce navigateur. Cette action est irréversible.
        </DialogDescription>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setOpen(false)}>
            Annuler
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              onConfirm();
              setOpen(false);
            }}
          >
            Supprimer
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
