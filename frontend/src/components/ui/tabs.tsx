// Adapted from shadcn/ui. MIT license: see THIRD_PARTY_NOTICES.md.
import * as React from "react";
import * as Primitive from "@radix-ui/react-tabs";
import { cn } from "../../utils";
export const Tabs = Primitive.Root;
export const TabsList = React.forwardRef<
  React.ElementRef<typeof Primitive.List>,
  React.ComponentPropsWithoutRef<typeof Primitive.List>
>(({ className, ...props }, ref) => (
  <Primitive.List
    ref={ref}
    className={cn(
      "inline-flex items-center gap-1 rounded-lg bg-secondary/70 p-1 text-muted-foreground",
      className,
    )}
    {...props}
  />
));
TabsList.displayName = "TabsList";
export const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof Primitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof Primitive.Trigger>
>(({ className, ...props }, ref) => (
  <Primitive.Trigger
    ref={ref}
    className={cn(
      "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-all data-[state=active]:bg-white data-[state=active]:text-foreground data-[state=active]:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = "TabsTrigger";
export const TabsContent = React.forwardRef<
  React.ElementRef<typeof Primitive.Content>,
  React.ComponentPropsWithoutRef<typeof Primitive.Content>
>(({ className, ...props }, ref) => (
  <Primitive.Content
    ref={ref}
    className={cn("min-h-0 flex-1 focus-visible:outline-none", className)}
    {...props}
  />
));
TabsContent.displayName = "TabsContent";
