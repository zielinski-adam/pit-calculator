import { useState } from "react";
import { HelpCircle } from "lucide-react";

interface InfoTooltipProps {
  text: string;
  ariaLabel?: string;
}

export function InfoTooltip({ text, ariaLabel }: InfoTooltipProps) {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-block">
      <button
        type="button"
        className="ml-1 inline-flex items-center text-muted-foreground hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-full"
        aria-label={ariaLabel ?? "Informacja"}
        onClick={() => setOpen((v) => !v)}
        onBlur={() => setOpen(false)}
      >
        <HelpCircle className="h-3.5 w-3.5" />
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md"
        >
          {text}
        </span>
      )}
    </span>
  );
}
