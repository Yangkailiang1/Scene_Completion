import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
export const phaseLabels: Record<string, string> = {
  pending: "待执行",
  transport_timeout: "请求超时",
  connection_failed: "连接中断",
  planned: "流程预告",
  awaiting_answer: "等待回答",
  rate_limit_wait: "限流冷却",
  rate_limited: "限流待恢复",
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
    : ["awaiting_review", "awaiting_answer", "rate_limit_wait"].includes(phase)
      ? "amber"
      : [
            "failed",
            "rejected",
            "budget_exhausted",
            "awaiting_configuration",
            "transport_timeout",
            "connection_failed",
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

export function failureText(value: any): string {
  const d = value?.transport_failure || value?.diagnostic || value;
  if (d?.failure_category === "transport_timeout") {
    const stage =
      d.timeout_kind === "total_deadline"
        ? "已达到整次生成时限"
        : d.phase === "stream_read"
          ? "模型生成期间等待超时"
          : d.phase === "connect_or_headers"
            ? "等待连接或首响应超时"
            : "模型请求超时（旧记录未区分具体阶段）";
    return (
      stage +
      (d.elapsed_seconds != null
        ? `，本次已等待${Math.round(d.elapsed_seconds)}秒`
        : "") +
      (d.incomplete_tools?.length
        ? `；${d.incomplete_tools.join("、")}参数尚未完整返回`
        : "") +
      "。未把不完整内容保存为产物，可调整等待时限后继续。"
    );
  }
  return value?.error || value?.reason || JSON.stringify(value);
}
