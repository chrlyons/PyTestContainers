import os
import time
import pytest
import subprocess
import psycopg2
from psycopg2 import OperationalError
from testcontainers.postgres import PostgresContainer
from customers import customers


def wait_for_db(host, port, user, password, db, timeout=120):
    start_time = time.time()
    retry_interval = 2
    while time.time() - start_time < timeout:
        try:
            conn = psycopg2.connect(
                host=host, port=port, user=user, password=password, dbname=db
            )
            conn.close()
            print("Database is ready")
            return True
        except OperationalError as e:
            print(f"Waiting for database... {e}")
            time.sleep(retry_interval)
            retry_interval = min(retry_interval * 2, 30)
    return False


@pytest.fixture(scope="function")
def postgres_container(request):
    version = request.param
    postgres = PostgresContainer(f"postgres:{version}")
    postgres.with_env("POSTGRES_USER", "test")
    postgres.with_env("POSTGRES_PASSWORD", "test")
    postgres.with_env("POSTGRES_DB", "test")
    postgres.start()

    # Ensure the container runs for at least a few seconds
    time.sleep(5)

    def remove_container():
        postgres.stop()

    request.addfinalizer(remove_container)
    return postgres


@pytest.fixture(scope="function", autouse=True)
def setup(postgres_container):
    postgres = postgres_container
    db_host = postgres.get_container_host_ip()
    db_port = postgres.get_exposed_port(5432)
    db_user = "test"
    db_password = "test"
    db_name = "test"

    os.environ["DB_HOST"] = db_host
    os.environ["DB_PORT"] = str(db_port)
    os.environ["DB_USERNAME"] = db_user
    os.environ["DB_PASSWORD"] = db_password
    os.environ["DB_NAME"] = db_name

    # Print debug information
    print(f"DB_HOST={db_host}")
    print(f"DB_PORT={db_port}")
    print(f"DB_USERNAME={db_user}")
    print(f"DB_PASSWORD={db_password}")
    print(f"DB_NAME={db_name}")

    # Wait for the database to be ready
    if not wait_for_db(
        host=db_host, port=db_port, user=db_user, password=db_password, db=db_name
    ):
        raise Exception("Database not ready")

    # Run Liquibase migrations using subprocess with environment variables and command-line arguments
    liquibase_command = [
        "liquibase",
        f"--changeLogFile=changelogs/db.changelog-master.yaml",
        f"--url=jdbc:postgresql://{db_host}:{db_port}/{db_name}",
        f"--username={db_user}",
        f"--password={db_password}",
        "update",
    ]
    attempt_count = 0
    max_attempts = 5
    while attempt_count < max_attempts:
        try:
            result = subprocess.run(
                liquibase_command, check=True, capture_output=True, text=True
            )
            print("Liquibase Output:\n", result.stdout)
            print("Liquibase Error Output:\n", result.stderr)
            break
        except subprocess.CalledProcessError as e:
            print(e.stderr)
            attempt_count += 1
            print(f"Attempt {attempt_count} failed, retrying...")
            time.sleep(5)
            if attempt_count >= max_attempts:
                raise


@pytest.mark.parametrize(
    "postgres_container", ["16-alpine", "15-alpine", "14-alpine"], indirect=True
)
def test_get_all_customers():
    customers.create_customer("Siva", "siva@gmail.com")
    customers.create_customer("James", "james@gmail.com")
    customers_list = customers.get_all_customers()
    assert len(customers_list) == 4


@pytest.mark.parametrize(
    "postgres_container", ["16-alpine", "15-alpine", "14-alpine"], indirect=True
)
def test_get_customer_by_email():
    customers.create_customer("John", "john@gmail.com")
    customer = customers.get_customer_by_email("john@gmail.com")
    assert customer.name == "John"
    assert customer.email == "john@gmail.com"


@pytest.mark.parametrize(
    "postgres_container", ["16-alpine", "15-alpine", "14-alpine"], indirect=True
)
def test_schema_and_data():
    db_host = os.environ["DB_HOST"]
    db_port = int(os.environ["DB_PORT"])
    db_user = os.environ["DB_USERNAME"]
    db_password = os.environ["DB_PASSWORD"]
    db_name = os.environ["DB_NAME"]

    conn = psycopg2.connect(
        host=db_host, port=db_port, user=db_user, password=db_password, dbname=db_name
    )
    cursor = conn.cursor()

    # Verify changesets applied
    cursor.execute("SELECT ID, AUTHOR FROM DATABASECHANGELOG")
    changelog_entries = cursor.fetchall()
    print("DATABASECHANGELOG Entries:", changelog_entries)
    assert len(changelog_entries) == 2

    # Verify table creation
    cursor.execute("SELECT to_regclass('public.customers')")
    assert cursor.fetchone()[0] is not None

    # Verify initial data insertion
    cursor.execute("SELECT name, email FROM customers")
    results = cursor.fetchall()
    print("Contents of customers table:", results)
    assert len(results) == 2
    expected_data = [
        ("TestUser1", "testuser1@example.com"),
        ("TestUser2", "testuser2@example.com"),
    ]
    for result in results:
        assert result in expected_data

    cursor.close()
    conn.close()
