"""Delete one bounded batch of expired login buckets; never delete active buckets."""

import argparse

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import get_engine


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.limit <= 10000:
        parser.error("limit must be between 1 and 10000")
    engine = get_engine(get_settings())
    try:
        with engine.begin() as conn:
            count = conn.execute(
                text("""WITH expired AS (
                SELECT bucket_key FROM auth_login_limits WHERE expires_at <= clock_timestamp()
                ORDER BY expires_at, bucket_key LIMIT :limit FOR UPDATE SKIP LOCKED
            ) DELETE FROM auth_login_limits a USING expired e
                WHERE a.bucket_key = e.bucket_key"""),
                {"limit": args.limit},
            ).rowcount
        print(f"Expired login buckets removed: {count}")
    except SQLAlchemyError:
        print("Cleanup failed; no changes saved.")
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
