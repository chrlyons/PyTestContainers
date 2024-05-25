import pytest
from customers import customers


@pytest.mark.parametrize(
    "postgres_container", ["16-alpine", "15-alpine", "14-alpine"], indirect=True
)
def test_get_all_customers(setup, db_connection, postgres_container):
    customers.create_customer("Siva", "siva@gmail.com")
    customers.create_customer("James", "james@gmail.com")
    customers_list = customers.get_all_customers()
    assert len(customers_list) == 2


@pytest.mark.parametrize(
    "postgres_container", ["16-alpine", "15-alpine", "14-alpine"], indirect=True
)
def test_get_customer_by_email(setup, db_connection, postgres_container):
    customers.create_customer("John", "john@gmail.com")
    customer = customers.get_customer_by_email("john@gmail.com")
    assert customer.name == "John"
    assert customer.email == "john@gmail.com"


@pytest.mark.parametrize(
    "postgres_container", ["16-alpine", "15-alpine", "14-alpine"], indirect=True
)
def test_schema_and_data(setup_with_liquibase, db_connection, postgres_container):
    # Verify changesets applied
    cursor = db_connection.cursor()
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
