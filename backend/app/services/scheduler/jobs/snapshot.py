"""Job snapshot quotidien (#212) — sauvegarde le journal de vie à 23h55."""


def run(session) -> str:
    from app.services.automatisations.snapshot import save_snapshot
    snap = save_snapshot(session)
    # Photo quotidienne du patrimoine net (#257), best-effort.
    try:
        from app.services.finance.patrimoine import record_net_worth_snapshot
        record_net_worth_snapshot(session)
    except Exception:
        pass
    return f"Snapshot {snap.date} sauvegardé"
