import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface StoryCardProps {
  title: string;
  /** One paragraph of plain language. The chart supports the claim; this states it. */
  body: ReactNode;
  /** What the chart actually measures. Never optional — a number without its definition invites
   *  the reader to invent one. */
  caption: string;
  children: ReactNode;
}

export const StoryCard = ({ title, body, caption, children }: StoryCardProps) => (
  <Card className="border border-border/60 shadow-[var(--shadow-card)]">
    <CardHeader className="pb-2">
      <CardTitle className="text-xl font-bold text-foreground sm:text-2xl">{title}</CardTitle>
    </CardHeader>
    <CardContent className="space-y-4">
      <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">{body}</p>
      {children}
      <p className="border-t border-border/50 pt-3 text-xs leading-relaxed text-muted-foreground/80">
        {caption}
      </p>
    </CardContent>
  </Card>
);
