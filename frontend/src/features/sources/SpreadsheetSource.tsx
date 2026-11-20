import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { afterSourceLayout, scrollSourceAnchor } from "./sourceScroll";

const rowsPerPage = 80;
const columnsPerPage = 24;

export function workbookSheet(name = "") {
  return name.match(/\.xlsx#(.+)$/i)?.[1];
}

function columnName(index: number): string {
  const prefix = Math.floor(index / 26);
  return (
    (prefix ? columnName(prefix - 1) : "") +
    String.fromCharCode(65 + (index % 26))
  );
}

function cellBounds(address?: string) {
  const match = address?.match(
    /^([A-Z]{1,3})[1-9]\d*(?::([A-Z]{1,3})[1-9]\d*)?$/i,
  );
  if (!match) return null;
  const index = (name: string) =>
    [...name.toUpperCase()].reduce(
      (value, char) => value * 26 + char.charCodeAt(0) - 64,
      0,
    ) - 1;
  const first = index(match[1]);
  const last = index(match[2] || match[1]);
  return first <= last && last < 16384 ? { first, last } : null;
}

function snapshotCells(text: string) {
  // This is the exact delimiter used when freezing Excel rows. Escaped pipes
  // inside a value and blank cells must not move subsequent Excel columns.
  if (!text.startsWith("| ") || !text.endsWith(" |")) return [];
  return text.slice(2, -2).split(" | ");
}

export function SpreadsheetSource({
  sheet,
  lines,
  start,
  end,
  address,
  jump,
}: {
  sheet: string;
  lines: { number: number; text: string }[];
  start: number;
  end: number;
  address?: string;
  jump: { line: number; revision: number };
}) {
  const grid = useRef<HTMLDivElement>(null);
  const bounds = cellBounds(address);
  const top = lines[0]?.number || 1;
  const bottom = lines.at(-1)?.number || top;
  const rowAnchor = Math.max(top, Math.min(bottom, jump.line));
  const jumpRow = Math.floor((rowAnchor - top) / rowsPerPage);
  const jumpColumn = Math.floor((bounds?.first || 0) / columnsPerPage);
  const [page, setPage] = useState({ jump, row: jumpRow, column: jumpColumn });
  const rowPage = page.jump === jump ? page.row : jumpRow;
  const columnPage = page.jump === jump ? page.column : jumpColumn;
  const firstRow = top + rowPage * rowsPerPage;
  const lastRow = Math.min(bottom, firstRow + rowsPerPage - 1);
  const { rows, widths } = useMemo(() => {
    const rows = new Map<number, string[]>();
    let widths = 0;
    for (const row of lines) {
      if (row.number < firstRow) continue;
      if (row.number > lastRow) break;
      const cells = snapshotCells(row.text);
      rows.set(row.number, cells);
      widths = Math.max(widths, cells.length);
    }
    return { rows, widths };
  }, [lines, firstRow, lastRow]);
  const width = Math.max(widths, (bounds?.last ?? 0) + 1);
  const firstColumn =
    Math.min(columnPage, Math.floor((width - 1) / columnsPerPage)) *
    columnsPerPage;
  const lastColumn = Math.min(width - 1, firstColumn + columnsPerPage - 1);
  const columns = Array.from(
    { length: lastColumn - firstColumn + 1 },
    (_, i) => firstColumn + i,
  );
  useLayoutEffect(() => {
    return afterSourceLayout(() => {
      const reader = grid.current;
      if (!reader) return;
      const target = reader.querySelector<HTMLElement>(
        `[data-source-line="${rowAnchor}"]`,
      );
      reader.scrollTop = 0;
      reader.scrollLeft = 0;
      scrollSourceAnchor(
        reader,
        target,
        reader.querySelector("thead")?.getBoundingClientRect().height || 0,
      );
      const marked = target?.querySelector<HTMLElement>(
        ".source-sheet-highlight",
      );
      if (marked) reader.scrollLeft = Math.max(0, marked.offsetLeft - 56);
    });
  }, [jump, rowAnchor, rowPage, firstColumn]);
  return (
    <div className="source-sheet-reader">
      <div className="source-evidence-toolbar source-sheet-toolbar">
        <strong>
          {sheet}
          {address ? `!${address}` : ""}
        </strong>
        <span>
          第 {firstRow}–{lastRow} 行
        </span>
        <button
          disabled={rowPage === 0}
          onClick={() =>
            setPage({ jump, row: rowPage - 1, column: columnPage })
          }
        >
          上一段
        </button>
        <button
          disabled={lastRow >= bottom}
          onClick={() =>
            setPage({ jump, row: rowPage + 1, column: columnPage })
          }
        >
          下一段
        </button>
        {width > columnsPerPage && (
          <>
            <button
              disabled={!firstColumn}
              onClick={() =>
                setPage({
                  jump,
                  row: rowPage,
                  column: firstColumn / columnsPerPage - 1,
                })
              }
            >
              向左翻列
            </button>
            <button
              disabled={lastColumn >= width - 1}
              onClick={() =>
                setPage({
                  jump,
                  row: rowPage,
                  column: firstColumn / columnsPerPage + 1,
                })
              }
            >
              向右翻列
            </button>
          </>
        )}
      </div>
      <div
        className="source-sheet-grid"
        ref={grid}
        tabIndex={0}
        aria-label="工作表滚动区域"
      >
        <table aria-label={`${sheet} 工作表`}>
          <thead>
            <tr>
              <th scope="col" aria-label="行号">
                #
              </th>
              {columns.map((column) => (
                <th scope="col" key={column}>
                  {columnName(column)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: lastRow - firstRow + 1 }, (_, offset) => {
              const number = firstRow + offset;
              const cells = rows.get(number) || [];
              return (
                <tr data-source-line={number} key={number}>
                  <th scope="row">{number}</th>
                  {columns.map((column) => (
                    <td
                      key={column}
                      data-cell={`${columnName(column)}${number}`}
                      className={
                        number >= start &&
                        number <= end &&
                        (!bounds ||
                          (column >= bounds.first && column <= bounds.last))
                          ? "source-sheet-highlight"
                          : undefined
                      }
                    >
                      {cells[column]
                        ?.replaceAll("\\|", "|")
                        .replaceAll("<br>", "\n")}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
