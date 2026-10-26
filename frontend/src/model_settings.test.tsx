import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { it, expect, vi, afterEach } from "vitest";
import { ModelSettings } from "./ModelSettings";
import { api } from "./api";
vi.mock("./api", () => ({
  api: vi.fn(),
  projectUrl: (p: string, s: string) => `/api/projects/${p}/${s}`,
}));
afterEach(() => vi.resetAllMocks());
it("selects only the models declared for each API-key connection", async () => {
  const saved = vi.fn();
  const mock = vi.mocked(api);
  mock.mockResolvedValue({
    revision: 1,
    accounts: [
      {
        id: "a",
        name: "Key A",
        base_url: "http://a/v1",
        models: ["model-a", "model-b"],
        credential_configured: true,
      },
      {
        id: "b",
        name: "Key B",
        base_url: "http://b/v1",
        models: ["model-c"],
        credential_configured: true,
      },
    ],
  });
  render(
    <ModelSettings
      project="p"
      config={{ model_account_id: "a", agent_model: "model-a" }}
      onSaved={saved}
    />,
  );
  await screen.findByRole("option", { name: "Key B" });
  fireEvent.change(screen.getByLabelText("API Key连接"), {
    target: { value: "b" },
  });
  expect((screen.getByLabelText("请求模型") as HTMLSelectElement).value).toBe(
    "model-c",
  );
  expect(screen.queryByRole("option", { name: "model-a" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "保存项目配置" }));
  await waitFor(() => expect(saved).toHaveBeenCalled());
  const call = mock.mock.calls.find((c) => c[1]?.method === "PUT");
  expect(JSON.parse(call![1]!.body as string)).toMatchObject({
    model_account_id: "b",
    agent_model: "model-c",
  });
});
it("account editor collects a key privately and submits a model list", async () => {
  const mock = vi.mocked(api);
  mock.mockResolvedValue({ revision: 0, accounts: [] });
  render(<ModelSettings project="p" config={{}} onSaved={() => {}} />);
  await waitFor(() => expect(mock).toHaveBeenCalled());
  fireEvent.click(screen.getByRole("button", { name: "新增API Key连接" }));
  expect(
    screen.getByLabelText("API Key（隐藏输入）").getAttribute("type"),
  ).toBe("password");
  fireEvent.change(screen.getByLabelText("连接名称"), {
    target: { value: "local" },
  });
  fireEvent.change(screen.getByLabelText("Base URL", { exact: true }), {
    target: { value: "http://a/v1" },
  });
  fireEvent.change(screen.getByLabelText("API Key（隐藏输入）"), {
    target: { value: "test-secret" },
  });
  fireEvent.change(screen.getByLabelText("此Key允许调用的模型"), {
    target: { value: "a\nb" },
  });
  mock.mockResolvedValueOnce({
    revision: 1,
    accounts: [
      {
        id: "new",
        name: "local",
        base_url: "http://a/v1",
        models: ["a", "b"],
        credential_configured: true,
      },
    ],
  });
  fireEvent.click(screen.getByRole("button", { name: "保存连接" }));
  await waitFor(() =>
    expect(mock).toHaveBeenCalledWith(
      "/api/model-accounts",
      expect.objectContaining({
        method: "PUT",
        body: expect.stringContaining('"models":["a","b"]'),
      }),
    ),
  );
  await screen.findByText(/连接已保存/);
  expect(screen.queryByDisplayValue("test-secret")).toBeNull();
});
