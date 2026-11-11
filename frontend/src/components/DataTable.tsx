import type { CSSProperties, ReactNode } from "react";
import { Card } from "./ui";

/** Glass card wrapping a table with a sticky header (sticks below the app's top bar + tab bar). */
export function DataTable({ children, minWidth = "60rem", caption }: { children: ReactNode; minWidth?: string; caption?: string }) {
  return (
    <Card className="hidden md:block">
      {/* overflow is only enabled below xl so the header can stick to the viewport on wide screens */}
      <div className="overflow-x-auto xl:overflow-visible">
        <table className="data-table" style={{ minWidth, "--stick": "7rem" } as CSSProperties}>
          {caption && <caption className="sr-only">{caption}</caption>}
          {children}
        </table>
      </div>
    </Card>
  );
}
