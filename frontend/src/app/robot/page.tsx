import RobotChat from "@/components/robot/RobotChat";

export default function RobotPage() {
  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <h1 className="text-xl font-semibold tracking-tight">Robot</h1>
        <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Assistant IA — chat avec accès à tes modules</p>
      </div>
      <div className="p-6">
        <RobotChat />
      </div>
    </div>
  );
}
