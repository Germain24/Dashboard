import { AlertTriangle } from "lucide-react";
import type { BuffettProgress, BuffettRunDetail, BuffettRunOut } from "@/lib/finance";
import type { OptProgress } from "./buffett-ui";
import { BuffettActionsPanel } from "./BuffettActionsPanel";
import { BuffettProgressPanel, BuffettRunsTimeline } from "./BuffettTabView";
import { BuffettRunDetailView } from "./BuffettRunDetailView";

type ContentProps = {
  error: string | null;
  reconnecting: boolean;
  progress: BuffettProgress | null;
  optProgress: OptProgress | null;
  runs: BuffettRunOut[];
  selected: BuffettRunDetail | null;
  starting: boolean;
  interrupted: boolean;
  paused: boolean;
  resumeAt: string | null;
  onStop: () => void;
  onStartRun: () => void;
  onOptimizationStarted: (value: OptProgress) => void;
  onError: (value: string | null) => void;
  onOpenRun: (id: number) => void;
  onDeleteRun: (id: number) => void;
  onBack: () => void;
  onReload: () => Promise<void>;
};

function ErrorNotice({ error, reconnecting }: Pick<ContentProps, "error" | "reconnecting">) {
  return (
    <>
      {error && (
        <p className="flex items-center gap-2 text-sm text-[var(--destructive)]">
          <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}
      {reconnecting && (
        <p className="text-xs text-[var(--muted-foreground)]" role="status">
          Reconnexion à la progression en cours…
        </p>
      )}
    </>
  );
}

function SelectedRun({ props }: { props: ContentProps & { selected: BuffettRunDetail } }) {
  return (
    <BuffettRunDetailView
      optProgress={props.optProgress}
      selected={props.selected}
      onBack={props.onBack}
      onError={props.onError}
      onReload={props.onReload}
    />
  );
}

function ActiveProgress({ props }: { props: ContentProps }) {
  if (!props.progress?.active && !props.interrupted) return null;
  return (
    <BuffettProgressPanel
      progress={props.progress}
      optProgress={props.optProgress}
      interrupted={props.interrupted}
      paused={props.paused}
      resumeAt={props.resumeAt}
      onStop={props.onStop}
      onOpenRun={props.onOpenRun}
    />
  );
}

function BuffettHome({ props }: { props: ContentProps }) {
  return (
    <div className="space-y-4">
      <ErrorNotice error={props.error} reconnecting={props.reconnecting} />
      <ActiveProgress props={props} />
      <BuffettActionsPanel
        starting={props.starting}
        progressActive={props.progress?.active === true}
        interrupted={props.interrupted}
        optProgress={props.optProgress}
        onStartRun={props.onStartRun}
        onOptimizationStarted={props.onOptimizationStarted}
        onStopOptimization={props.onStop}
        onError={props.onError}
      />
      <BuffettRunsTimeline
        runs={props.runs}
        optProgress={props.optProgress}
        onOpen={props.onOpenRun}
        onDelete={props.onDeleteRun}
      />
    </div>
  );
}

export function BuffettTabContent(props: ContentProps) {
  return props.selected ? (
    <SelectedRun props={{ ...props, selected: props.selected }} />
  ) : (
    <BuffettHome props={props} />
  );
}
