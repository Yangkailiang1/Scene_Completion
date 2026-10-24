import { it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./components/ui/tabs";
import { readFileSync } from "node:fs";
const styles = readFileSync("src/styles.css", "utf8");

it("inactive scroll tabs stay out of layout instead of consuming output height", () => {
  const style = document.createElement("style");
  style.textContent = styles.replace(/@tailwind[^;]+;/g, "");
  document.head.append(style);
  try {
    render(
      <Tabs defaultValue="stream" className="node-tabs">
        <TabsList>
          <TabsTrigger value="stream">输出</TabsTrigger>
          <TabsTrigger value="artifacts">产物</TabsTrigger>
        </TabsList>
        <TabsContent value="stream" className="stream-panel">
          日志正文
        </TabsContent>
        <TabsContent value="artifacts" className="panel-scroll">
          产物内容
        </TabsContent>
      </Tabs>,
    );
    const panels = screen.getAllByRole("tabpanel", { hidden: true });
    expect(getComputedStyle(panels[1]).display).toBe("none");
    expect(getComputedStyle(panels[0]).display).toBe("grid");
    fireEvent.mouseDown(screen.getByRole("tab", { name: "产物" }), {
      button: 0,
      ctrlKey: false,
    });
    expect(getComputedStyle(panels[0]).display).toBe("none");
    expect(getComputedStyle(panels[1]).display).toBe("block");
  } finally {
    style.remove();
  }
});
