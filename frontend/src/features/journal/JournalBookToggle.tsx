import React from "react";
import { BookOpen, Briefcase, Scale } from "lucide-react";

export type JournalBook = "paper" | "real" | "compare";

interface JournalBookToggleProps {
  currentBook?: JournalBook;
  value?: JournalBook;
  onSelectBook?: (book: JournalBook) => void;
  onChange?: (book: JournalBook) => void;
  disabled?: boolean;
}

export const JournalBookToggle: React.FC<JournalBookToggleProps> = ({
  currentBook,
  value,
  onSelectBook,
  onChange,
  disabled = false,
}) => {
  const active = value || currentBook || "paper";
  const handleSelect = (b: JournalBook) => {
    if (onChange) onChange(b);
    if (onSelectBook) onSelectBook(b);
  };
  return (
    <div
      role="group"
      aria-label="Pilihan Buku Jurnal"
      className="inline-flex items-center p-1 bg-surface border border-border rounded-xl shadow-inner"
    >
      <button
        id="btn-book-paper"
        type="button"
        disabled={disabled}
        onClick={() => handleSelect("paper")}
        className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs md:text-sm font-medium transition-all ${
          active === "paper"
            ? "bg-accent text-accent-fg shadow-sm font-semibold"
            : "text-muted hover:text-fg hover:bg-surface-elevated"
        }`}
      >
        <BookOpen className="w-4 h-4" aria-hidden="true" />
        <span>Buku Paper</span>
      </button>

      <button
        id="btn-book-real"
        type="button"
        disabled={disabled}
        onClick={() => handleSelect("real")}
        className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs md:text-sm font-medium transition-all ${
          active === "real"
            ? "bg-accent text-accent-fg shadow-sm font-semibold"
            : "text-muted hover:text-fg hover:bg-surface-elevated"
        }`}
      >
        <Briefcase className="w-4 h-4" aria-hidden="true" />
        <span>Jurnal Real</span>
      </button>

      <button
        id="btn-book-compare"
        type="button"
        disabled={disabled}
        onClick={() => handleSelect("compare")}
        className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs md:text-sm font-medium transition-all ${
          active === "compare"
            ? "bg-accent text-accent-fg shadow-sm font-semibold"
            : "text-muted hover:text-fg hover:bg-surface-elevated"
        }`}
      >
        <Scale className="w-4 h-4" aria-hidden="true" />
        <span>Bandingkan</span>
      </button>
    </div>
  );
};
