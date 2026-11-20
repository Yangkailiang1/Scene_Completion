export function afterSourceLayout(callback: () => void) {
  const frame = requestAnimationFrame(callback);
  return () => cancelAnimationFrame(frame);
}

export function scrollSourceAnchor(
  container: HTMLElement,
  target: HTMLElement | null | undefined,
  inset = 24,
) {
  if (!target || !container.contains(target)) return;
  container.scrollTop +=
    target.getBoundingClientRect().top -
    container.getBoundingClientRect().top -
    inset;
}
