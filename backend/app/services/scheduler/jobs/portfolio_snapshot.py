def run(session):
    try:
        from app.services.finance.external_accounts import refresh_external_accounts
        refresh_external_accounts(session, force=True)
        from app.services.finance.snapshots import create_daily_snapshot
        return create_daily_snapshot(session)
    except Exception as e:
        return f"Snapshot skipped: {e}"
