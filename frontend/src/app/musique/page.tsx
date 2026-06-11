import Musique from "@/components/musique/Musique";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const metadata = { title: "Musique — Mission Control" };

export default function MusiquePage() {
  return (
    <ErrorBoundary label="Musique">
      <Musique />
    </ErrorBoundary>
  );
}
