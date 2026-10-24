// Adapted from shadcn/ui. MIT license: see THIRD_PARTY_NOTICES.md.
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../utils";
const variants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
        outline:
          "border border-input bg-white hover:bg-accent hover:text-accent-foreground",
        ghost: "hover:bg-secondary hover:text-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "bg-destructive text-white hover:bg-destructive/90",
      },
      size: {
        default: "h-9 px-3 py-2",
        sm: "h-8 px-2.5 text-xs",
        icon: "h-8 w-8",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);
export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof variants> {
  asChild?: boolean;
}
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Component = asChild ? Slot : "button";
    return (
      <Component
        className={cn(variants({ variant, size }), className)}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
