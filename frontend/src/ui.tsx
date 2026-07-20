import { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`cropmarks bg-card border border-line p-5 ${className}`}>
      {children}
    </div>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="eyebrow mb-1">{children}</div>;
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <div>
      <div className="mono text-2xl text-ink">{value}</div>
      <div className="eyebrow mt-1">{label}</div>
      {sub && <div className="text-xs text-ink-2 mt-0.5">{sub}</div>}
    </div>
  );
}

export function Button({
  children,
  onClick,
  kind = "primary",
  disabled,
}: {
  children: ReactNode;
  onClick?: () => void;
  kind?: "primary" | "quiet" | "danger";
  disabled?: boolean;
}) {
  const styles = {
    primary: "bg-press text-white hover:bg-ink",
    quiet: "bg-transparent text-ink border border-line hover:border-ink",
    danger: "bg-transparent text-reg border border-reg/40 hover:bg-reg hover:text-white",
  }[kind];
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`px-3.5 py-1.5 text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${styles}`}
    >
      {children}
    </button>
  );
}

const STATUS_INK: Record<string, string> = {
  intake: "text-ink-2 border-line",
  drafting: "text-press border-press/40",
  review: "text-reg border-reg/40",
  final: "text-ok border-ok/40",
  delivered: "text-ink border-ink",
};

export function StatusTag({ status }: { status: string }) {
  return (
    <span className={`mono text-[10px] uppercase tracking-widest border px-2 py-0.5 ${STATUS_INK[status] ?? STATUS_INK.intake}`}>
      {status}
    </span>
  );
}

export function Progress({ value, note }: { value: number; note?: string | null }) {
  return (
    <div>
      <div className="h-1 bg-line">
        <div className="h-1 bg-press transition-all" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      {note && <div className="mono text-[10px] text-ink-2 mt-1">{note}</div>}
    </div>
  );
}

/** Single-hue labeled bar row — magnitude is the job, identity lives in the
 * label, so one press-blue hue and no rainbow. */
export function BarRow({ label, value, max, format }: { label: string; value: number; max: number; format: (v: number) => string }) {
  const w = max > 0 ? Math.max(2, (value / max) * 100) : 0;
  return (
    <div className="grid grid-cols-[10rem_1fr_5rem] items-center gap-3 py-1" title={`${label}: ${format(value)}`}>
      <div className="text-xs text-ink-2 truncate">{label}</div>
      <div className="h-4 bg-press-soft">
        <div className="h-4 bg-press" style={{ width: `${w}%`, borderRadius: "0 2px 2px 0" }} />
      </div>
      <div className="mono text-xs text-right">{format(value)}</div>
    </div>
  );
}
