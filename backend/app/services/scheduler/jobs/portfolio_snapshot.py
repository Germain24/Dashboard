def run(session):
    try:
        from app.services.finance.snapshots import create_daily_snapshot
        return create_daily_snapshot(session)
    except Exception as e:
        return f"Snapshot skipped: {e}"
