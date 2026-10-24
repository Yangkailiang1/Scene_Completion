import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
export const phaseLabels: Record<string, string> = {
  pending: "待执行",
  preparing: "准备中",
  model_wait: "等待模型",
  streaming: "输出中",
  tool_running: "工具执行中",
  validating: "校验中",
  saving: "保存中",
  awaiting_review: "待审核",
  dependency_wait: "等待依赖",
  complete: "已完成",
  failed: "失败",
  rejected: "校验未通过",
  budget_exhausted: "额度不足",
  awaiting_configuration: "待配置",
  disabled: "未启用",
};
export const roleLabels: Record<string, string> = {
  modeler: "建模器",
  checker: "检查器",
  recommender: "推荐器",
};
export function phaseColor(phase: string) {
  return phase === "complete"
    ? "green"
    : phase === "awaiting_review"
      ? "amber"
      : [
            "failed",
            "rejected",
            "budget_exhausted",
            "awaiting_configuration",
          ].includes(phase)
        ? "red"
        : [
              "model_wait",
              "streaming",
              "tool_running",
              "validating",
              "saving",
              "preparing",
            ].includes(phase)
          ? "blue"
          : "gray";
}
export function duration(seconds: number | null) {
  if (seconds === null) return "—";
  if (seconds < 60) return `${Math.floor(seconds)}秒`;
  return `${Math.floor(seconds / 60)}分${Math.floor(seconds % 60)}秒`;
}
export function display(value: any): string {
  return value === null || value === undefined
    ? "待确认"
    : typeof value === "object"
      ? JSON.stringify(value, null, 2)
      : String(value);
}
