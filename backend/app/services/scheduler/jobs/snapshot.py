"""Job snapshot quotidien (#212) — sauvegarde le journal de vie à 23h55."""


def run(session) -> str:
    from app.services.automatisations.snapshot import save_snapshot
    snap = save_snapshot(session)
    return f"Snapshot {snap.date} sauvegardé"
