const humanSecurity = new Set(["human.authentication", "human.authorization"]);

export const retiredServiceSecurity = new Set([
  "service_relation.authentication",
  "service_relation.authorization",
]);

export function securityMountAllowed(
  key: string,
  target?: string,
  step?: {
    direction: string;
    kind: string;
    sender: { id: string; type: string };
    receiver: { id: string; type: string };
  },
) {
  if (retiredServiceSecurity.has(key)) return false;
  if (!humanSecurity.has(key)) return true;
  return (
    target === "sender" &&
    step?.direction === "request" &&
    step.kind !== "action" &&
    step.sender.id !== step.receiver.id &&
    step.sender.type === "human" &&
    step.receiver.type === "service"
  );
}
