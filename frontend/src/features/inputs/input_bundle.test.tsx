import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { InputBundlePicker } from "./InputBundlePicker";

function preview() {
  return {
    preview_hash: "frozen",
    valid: true,
    complete: true,
    missing: [],
    issues: [],
    ignored: [{ name: "fusion.json", reason: "非五类输入" }],
    files: [
      {
        role: "RR",
        label: "RR用例与已有场景",
        name: "structure_model.json",
        path: "RR/structure_model.json",
        target_nodes: ["rr-use-cases"],
      },
      {
        role: "api_extraction",
        label: "接口映射与请求参数",
        name: "api_extraction.json",
        path: "api_extraction.json",
        target_nodes: ["api-parameters-part-*"],
      },
    ],
  };
}

test("absolute paths preview before apply and keep partial adoption explicit", async () => {
  const calls: any[] = [];
  const imported = vi.fn();
  const close = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: any, init: any) => ({
      ok: true,
      json: async () => {
        calls.push({ url: String(url), body: JSON.parse(init.body) });
        return String(url).endsWith("/preview") ? preview() : { saved: true };
      },
    })),
  );
  render(
    <InputBundlePicker project="p" onImported={imported} onClose={close} />,
  );
  fireEvent.click(screen.getByRole("button", { name: "分别指定绝对路径" }));
  fireEvent.change(screen.getByLabelText("RR结构模型绝对路径"), {
    target: { value: "C:\\输入\\RR\\structure_model.json" },
  });
  fireEvent.change(screen.getByLabelText("接口抽取绝对路径"), {
    target: { value: "C:\\输入\\api_extraction.json" },
  });
  fireEvent.click(screen.getByRole("button", { name: "识别指定文件" }));
  await screen.findByText("RR用例与已有场景");
  expect(calls).toHaveLength(1);
  expect(calls[0].url).toContain("input-bundles/preview");
  expect(screen.getByText(/缺少的响应继续抽取/)).toBeTruthy();
  fireEvent.click(
    screen.getByLabelText("采用已校验的部分字段和属性，其余仍由对应节点补齐"),
  );
  fireEvent.click(screen.getByRole("button", { name: "确认导入" }));
  await waitFor(() => expect(imported).toHaveBeenCalledOnce());
  expect(calls[1].url).toBe("/api/projects/p/input-bundles");
  expect(calls[1].body).toMatchObject({
    expected_hash: "frozen",
    adopt_partial: true,
    replace: false,
    paths: { RR: "C:\\输入\\RR\\structure_model.json" },
  });
  expect(close).toHaveBeenCalledOnce();
});

test("browser folder reads JSON and excludes Skill instructions", async () => {
  const jsonFile = new File(["{}"], "arbitrary.json", {
    type: "application/json",
  });
  Object.defineProperty(jsonFile, "webkitRelativePath", {
    value: "input/SR/arbitrary.json",
  });
  Object.defineProperty(jsonFile, "text", {
    value: vi.fn().mockResolvedValue("{}"),
  });
  const skill = new File(["never execute"], "SKILL.md");
  const readSkill = vi.fn();
  Object.defineProperty(skill, "text", { value: readSkill });
  const calls: any[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: any, init: any) => ({
      ok: true,
      json: async () => {
        calls.push(JSON.parse(init.body));
        return preview();
      },
    })),
  );
  render(
    <InputBundlePicker
      project="p"
      initialFiles={[jsonFile, skill]}
      onClose={() => {}}
      onImported={() => {}}
    />,
  );
  await screen.findByText("RR用例与已有场景");
  expect(calls[0].files).toHaveLength(1);
  expect(calls[0].files[0].relative_path).toBe("input/SR/arbitrary.json");
  expect(readSkill).not.toHaveBeenCalled();
});

test("new project uploads five JSON files directly without Markdown form", async () => {
  const calls: any[] = [];
  const imported = vi.fn();
  const close = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: any, init: any) => ({
      ok: true,
      json: async () => {
        calls.push({ url: String(url), body: JSON.parse(init.body) });
        return String(url).endsWith("/preview")
          ? preview()
          : { id: "created-project" };
      },
    })),
  );
  render(
    <InputBundlePicker project="" onImported={imported} onClose={close} />,
  );
  fireEvent.change(screen.getByLabelText("五文件新项目名称"), {
    target: { value: "上传验收" },
  });
  const files = [
    "rr.json",
    "sr.json",
    "功能树.json",
    "api_extraction.json",
    "recovered_usecases.json",
  ].map((name) => {
    const f = new File(["{}"], name);
    Object.defineProperty(f, "text", { value: async () => "{}" });
    return f;
  });
  fireEvent.change(screen.getByLabelText("选择五份JSON文件"), {
    target: { files },
  });
  await screen.findByText("RR用例与已有场景");
  fireEvent.click(screen.getByRole("button", { name: "确认导入" }));
  await waitFor(() =>
    expect(imported).toHaveBeenCalledWith({ id: "created-project" }),
  );
  expect(calls[1].url).toBe("/api/projects/from-input-bundle");
  expect(calls[1].body.files).toHaveLength(5);
  expect(calls[1].body.name).toBe("上传验收");
  expect(calls[1].body.expected_hash).toBe("frozen");
});
