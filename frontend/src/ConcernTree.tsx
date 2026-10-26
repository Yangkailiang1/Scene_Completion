import { useState } from "react";
type Branch = {
  name: string;
  path: string;
  children: Record<string, Branch>;
  leaves: [string, any][];
};
function ids(b: Branch): Set<string> {
  return new Set([
    ...b.leaves.map(([k]) => k),
    ...Object.values(b.children).flatMap((c) => [...ids(c)]),
  ]);
}
function BranchView({
  b,
  project,
  selected,
  pick,
}: {
  b: Branch;
  project: string;
  selected: string;
  pick: (k: string, d: any) => void;
}) {
  const storage = `concern-tree:${project}:${b.path}`;
  const [open, setOpen] = useState(
    () => localStorage.getItem(storage) !== "closed",
  );
  return (
    <details
      open={open}
      onToggle={(e) => {
        const value = e.currentTarget.open;
        setOpen(value);
        localStorage.setItem(storage, value ? "open" : "closed");
      }}
    >
      <summary>
        {b.name}
        <small>{ids(b).size} 项定义</small>
      </summary>
      {b.leaves.map(([k, d]) => (
        <button
          key={k}
          className={selected === k ? "active" : ""}
          onClick={() => pick(k, d)}
        >
          <strong>
            {d.label}
            {d.enabled === false ? "（已停用）" : ""}
          </strong>
          <span>{k}</span>
        </button>
      ))}
      {Object.values(b.children).map((c) => (
        <BranchView
          key={c.path}
          b={c}
          project={project}
          selected={selected}
          pick={pick}
        />
      ))}
    </details>
  );
}
export function ConcernTree({
  definitions,
  paths,
  project,
  selected,
  query,
  pick,
}: {
  definitions: [string, any][];
  paths: Record<string, string[][]>;
  project: string;
  selected: string;
  query: string;
  pick: (k: string, d: any) => void;
}) {
  const root: Branch = { name: "root", path: "", children: {}, leaves: [] };
  for (const [key, d] of definitions)
    for (const path of paths[key] || [["待归类"]]) {
      if (
        ![key, d.label, d.description, ...path]
          .join(" ")
          .toLowerCase()
          .includes(query.toLowerCase())
      )
        continue;
      let node = root;
      for (const name of path) {
        const id = node.path + "/" + name;
        node.children[name] ||= { name, path: id, children: {}, leaves: [] };
        node = node.children[name];
      }
      node.leaves.push([key, d]);
    }
  return (
    <div className="concern-tree" aria-label="关注点分类树">
      <p className="muted">
        输入／输出可引用同一稳定定义，展示路径不重复计分。
      </p>
      {Object.values(root.children).sort((a, b) => {
        const order = ["人类Actor关注点", "Service关注点", "待归类"];
        const rank = (name: string) => {
          const i = order.indexOf(name);
          return i < 0 ? order.length : i;
        };
        return rank(a.name) - rank(b.name);
      }).map((b) => (
        <BranchView
          key={b.path}
          b={b}
          project={project}
          selected={selected}
          pick={pick}
        />
      ))}
      {!Object.keys(root.children).length && <p>无匹配的关注点</p>}
    </div>
  );
}
