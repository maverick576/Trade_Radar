import React from "react";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "bull" | "bear" | "neutral" | "warn" | "accent";
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  className = "",
  variant = "default",
  dot = false,
  ...props
}) => {
  const variantStyles = {
    default: "bg-surface-2 text-muted border-border",
    bull: "bg-bull/15 text-bull border-bull/30",
    bear: "bg-bear/15 text-bear border-bear/30",
    neutral: "bg-neutral/15 text-neutral border-neutral/30",
    warn: "bg-warn/15 text-warn border-warn/30",
    accent: "bg-accent/15 text-accent border-accent/30",
  };

  const dotStyles = {
    default: "bg-muted",
    bull: "bg-bull",
    bear: "bg-bear",
    neutral: "bg-neutral",
    warn: "bg-warn",
    accent: "bg-accent",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotStyles[variant]}`}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
};
