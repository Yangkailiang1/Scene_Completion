import fs from "node:fs";
import path from "node:path";
const root = path.resolve(import.meta.dirname, "..");
const lock = JSON.parse(
  fs.readFileSync(path.join(root, "package-lock.json"), "utf8"),
);
const sections = [
  "Frontend third-party notices\n\nReact Flow, React, Radix UI and the libraries listed below are distributed in the compiled local web application. Button and Tabs components adapt shadcn/ui under MIT. No external CDN is used.\n",
  fs.readFileSync(path.join(root, "licenses/shadcn-ui.txt"), "utf8"),
];
for (const [name, record] of Object.entries(lock.packages)) {
  if (!name || record.dev) continue;
  const folder = path.join(root, name);
  const p = JSON.parse(
    fs.readFileSync(path.join(folder, "package.json"), "utf8"),
  );
  const files = fs
    .readdirSync(folder)
    .filter(
      (n) =>
        /^(licen[cs]e|copying|notice)(\.|$)/i.test(n) &&
        fs.statSync(path.join(folder, n)).isFile(),
    );
  sections.push(
    `\n${"=".repeat(70)}\n${p.name}@${p.version}\nLicense: ${p.license || record.license || "See package notices"}\n${p.homepage || ""}\n` +
      files
        .map((f) => fs.readFileSync(path.join(folder, f), "utf8"))
        .join("\n"),
  );
}
fs.mkdirSync(path.join(root, "public"), { recursive: true });
fs.writeFileSync(
  path.join(root, "public/third-party-licenses.txt"),
  sections.join("\n"),
);
