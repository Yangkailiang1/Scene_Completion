import { useEffect, useRef, useState } from "react";

export function EditableCell({
  value,
  label,
  readonly,
  onChange,
}: {
  value?: string;
  label: string;
  readonly?: boolean;
  onChange: (value: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value || "");
  const cancelled = useRef(false);
  useEffect(() => {
    if (!editing) setText(value || "");
  }, [value, editing]);
  if (readonly) return <span>{value}</span>;
  function commit() {
    if (!cancelled.current && text !== (value || "")) onChange(text);
    setEditing(false);
  }
  return editing ? (
    <textarea
      autoFocus
      aria-label={label}
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          cancelled.current = true;
          setEditing(false);
        } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
          e.preventDefault();
          commit();
        }
      }}
    />
  ) : (
    <button
      className="ssd-editable-cell"
      aria-label={label}
      onClick={() => {
        cancelled.current = false;
        setText(value || "");
        setEditing(true);
      }}
    >
      {value || "点击填写"}
    </button>
  );
}
