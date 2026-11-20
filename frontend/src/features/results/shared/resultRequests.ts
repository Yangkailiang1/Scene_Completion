import { api, projectUrl } from "../../../shared/api";

const entries = new Map<
  string,
  { promise: Promise<any>; expires: number; project: string }
>();
const epochs = new Map<string, string>();
export function invalidateResults(project?: string) {
  for (const [key, entry] of entries)
    if (project === undefined || entry.project === project) entries.delete(key);
}
export function setResultEpoch(project: string, epoch?: string) {
  if (epoch !== undefined && epochs.get(project) !== epoch) {
    epochs.set(project, epoch);
    invalidateResults(project);
  }
}
function resultRead(project: string, suffix: string, body?: string) {
  const url = projectUrl(project, suffix),
    key = body === undefined ? url : `${url}\n${body}`,
    found = entries.get(key);
  if (found && found.expires > Date.now()) return found.promise;
  const entry = {
    promise: api(
      url,
      body === undefined ? undefined : { method: "POST", body },
    ),
    expires: Infinity,
    project,
  };
  entries.set(key, entry);
  entry.promise.then(
    () => {
      entry.expires = Date.now() + 2000;
    },
    () => {
      if (entries.get(key) === entry) entries.delete(key);
    },
  );
  if (entries.size > 16) entries.delete(entries.keys().next().value!);
  return entry.promise;
}

export function resultGet(project: string, suffix: string) {
  return resultRead(project, suffix);
}

export function resultSummary(project: string, suffix: string, body: object) {
  return resultRead(project, suffix, JSON.stringify(body));
}
