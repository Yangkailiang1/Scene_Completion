import { useEffect, useState } from "react";
import { getSsdResultIndex } from "./ssd/api";
import { SsdResultsView } from "./ssd/SsdResultsView";
import { SavedResultsView } from "./saved/SavedResultsView";
export function ResultsView(props: { project: string; liveVersion?: string }) {
  const [modern, setModern] = useState<any>(null);
  useEffect(() => {
    let live = true;
    getSsdResultIndex(props.project)
      .then((value) => {
        if (live && value?.version === "ssd-case-v1" && value.cases?.length)
          setModern({ project: props.project, index: value });
      })
      .catch(() => {
        /* Existing projects still use their saved result view. */
      });
    return () => {
      live = false;
    };
  }, [props.project, props.liveVersion]);
  return modern?.project === props.project ? (
    <SsdResultsView
      key={props.project}
      {...props}
      initialIndex={modern.index}
    />
  ) : (
    <SavedResultsView {...props} />
  );
}
