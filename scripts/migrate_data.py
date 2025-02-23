import sqlite3
import psycopg2
from datetime import datetime
import json
from ..app.core.config import get_settings
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

settings = get_settings()


def connect_postgres():
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        print("Connected to PostgreSQL successfully!")
        return conn
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        sys.exit(1)


def connect_sqlite():
    """Connect to SQLite database"""
    try:
        conn = sqlite3.connect("jobs.db")  # Update path if different
        print("Connected to SQLite successfully!")
        return conn
    except Exception as e:
        print(f"Error connecting to SQLite: {e}")
        sys.exit(1)


def migrate_jobs(sqlite_cur, pg_cur):
    """Migrate jobs table"""
    try:
        # Get jobs from SQLite
        sqlite_cur.execute("SELECT * FROM jobs")
        jobs = sqlite_cur.fetchall()

        if not jobs:
            print("No jobs found in SQLite database")
            return

        # Get column names
        columns = [description[0] for description in sqlite_cur.description]

        # Prepare INSERT statement
        columns_str = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        insert_query = f"INSERT INTO jobs ({columns_str}) VALUES ({placeholders}) ON CONFLICT (detail_url) DO NOTHING"

        # Insert jobs into PostgreSQL
        for job in jobs:
            # Convert any datetime strings to proper datetime objects
            processed_job = list(job)
            for i, value in enumerate(processed_job):
                if isinstance(value, str) and "date" in columns[i].lower():
                    try:
                        processed_job[i] = datetime.strptime(value, "%Y-%m-%d").date()
                    except ValueError:
                        pass

            pg_cur.execute(insert_query, processed_job)

        print(f"Successfully migrated {len(jobs)} jobs")

    except Exception as e:
        print(f"Error migrating jobs: {e}")
        raise


def migrate_scraping_history(sqlite_cur, pg_cur):
    """Migrate scraping_history table"""
    try:
        # Get scraping history from SQLite
        sqlite_cur.execute("SELECT * FROM scraping_history")
        history = sqlite_cur.fetchall()

        if not history:
            print("No scraping history found in SQLite database")
            return

        # Get column names
        columns = [description[0] for description in sqlite_cur.description]

        # Prepare INSERT statement
        columns_str = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        insert_query = (
            f"INSERT INTO scraping_history ({columns_str}) VALUES ({placeholders})"
        )

        # Insert history into PostgreSQL
        for record in history:
            # Convert any datetime strings to proper datetime objects
            processed_record = list(record)
            for i, value in enumerate(processed_record):
                if isinstance(value, str) and (
                    "time" in columns[i].lower() or "date" in columns[i].lower()
                ):
                    try:
                        processed_record[i] = datetime.fromisoformat(
                            value.replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass

            pg_cur.execute(insert_query, processed_record)

        print(f"Successfully migrated {len(history)} scraping history records")

    except Exception as e:
        print(f"Error migrating scraping history: {e}")
        raise


def migrate_settings(sqlite_cur, pg_cur):
    """Migrate settings table"""
    try:
        # Get settings from SQLite
        sqlite_cur.execute("SELECT * FROM settings")
        settings_data = sqlite_cur.fetchall()

        if not settings_data:
            print("No settings found in SQLite database")
            return

        # Get column names
        columns = [description[0] for description in sqlite_cur.description]

        # Prepare INSERT statement
        columns_str = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        insert_query = f"INSERT INTO settings ({columns_str}) VALUES ({placeholders})"

        # Insert settings into PostgreSQL
        for setting in settings_data:
            # Convert any JSON strings to proper JSON objects
            processed_setting = list(setting)
            for i, value in enumerate(processed_setting):
                if isinstance(value, str) and "config" in columns[i].lower():
                    try:
                        processed_setting[i] = json.loads(value)
                    except ValueError:
                        pass

            pg_cur.execute(insert_query, processed_setting)

        print(f"Successfully migrated {len(settings_data)} settings records")

    except Exception as e:
        print(f"Error migrating settings: {e}")
        raise


def main():
    sqlite_conn = None
    pg_conn = None

    try:
        # Connect to both databases
        sqlite_conn = connect_sqlite()
        pg_conn = connect_postgres()

        sqlite_cur = sqlite_conn.cursor()
        pg_cur = pg_conn.cursor()

        # Start migration
        print("\nStarting data migration...")

        # Migrate each table
        migrate_jobs(sqlite_cur, pg_cur)
        migrate_scraping_history(sqlite_cur, pg_cur)
        migrate_settings(sqlite_cur, pg_cur)

        # Commit the transaction
        pg_conn.commit()
        print("\nMigration completed successfully!")

    except Exception as e:
        if pg_conn:
            pg_conn.rollback()
        print(f"\nError during migration: {e}")
        raise

    finally:
        # Close connections
        if sqlite_conn:
            sqlite_conn.close()
        if pg_conn:
            pg_conn.close()
        print("\nConnections closed.")


if __name__ == "__main__":
    main()
