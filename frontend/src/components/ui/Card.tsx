import React from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "surface-2" | "outline";
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ children, className = "", variant = "default", ...props }, ref) => {
    const bgStyles = {
      default: "bg-surface border-border",
      "surface-2": "bg-surface-2 border-border",
      outline: "bg-transparent border-border",
    };

    return (
      <div
        ref={ref}
        className={`rounded-panel border p-5 md:p-6 transition-all duration-200 ${bgStyles[variant]} ${className}`}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = "Card";
