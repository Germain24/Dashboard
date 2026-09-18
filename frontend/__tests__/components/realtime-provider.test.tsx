import { act, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  RealtimeProvider,
  useRealtimeEvent,
  useRealtimeStatus,
} from "@/components/RealtimeProvider";

class FakeEventSource {
  static latest: FakeEventSource;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  close = vi.fn();

  constructor(public url: string) {
    FakeEventSource.latest = this;
  }

  emit(event: object) {
    this.onmessage?.({ data: JSON.stringify(event) } as MessageEvent<string>);
  }
}

function Consumer() {
  const status = useRealtimeStatus();
  const [value, setValue] = useState("none");
  useRealtimeEvent<{ value: string }>("direct", ({ data }) => {
    if (data) setValue(data.value);
  });
  return <div>{status}:{value}</div>;
}

afterEach(() => vi.unstubAllGlobals());

describe("RealtimeProvider", () => {
  it("distribue les données, invalide les clés et ferme la connexion", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries").mockResolvedValue();
    const view = render(
      <QueryClientProvider client={client}>
        <RealtimeProvider><Consumer /></RealtimeProvider>
      </QueryClientProvider>,
    );

    expect(FakeEventSource.latest.url).toBe("/api/events");
    act(() => FakeEventSource.latest.onopen?.());
    act(() => FakeEventSource.latest.emit({
      id: 1,
      topic: "direct",
      timestamp: "2026-01-01T00:00:00Z",
      data: { value: "live" },
      invalidate: [["finance", "state"]],
    }));
    expect(screen.getByText("connected:live")).toBeInTheDocument();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["finance", "state"] });

    const invalidationsBeforeProgress = invalidate.mock.calls.length;
    act(() => FakeEventSource.latest.emit({
      id: 2,
      topic: "finance.buffett.progress",
      timestamp: "2026-01-01T00:00:00Z",
      data: { done: 123 },
      invalidate: [["finance", "buffett"]],
    }));
    expect(invalidate).toHaveBeenCalledTimes(invalidationsBeforeProgress);

    act(() => FakeEventSource.latest.emit({
      id: 3,
      topic: "resync_required",
      timestamp: "2026-01-01T00:00:01Z",
    }));
    expect(invalidate).toHaveBeenCalledWith();
    view.unmount();
    expect(FakeEventSource.latest.close).toHaveBeenCalledOnce();
  });
});
