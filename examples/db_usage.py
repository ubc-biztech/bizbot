"""
Example usage of the DynamoDB helper utilities.

This demonstrates the main database operations available in the db module.
"""

import asyncio
from bots.db import db


async def example_usage():
    """Demonstrate common database operations."""

    # 1. CREATE - Insert a new item
    print("1. Creating new user...")
    new_user = {
        "id": "user-123",
        "name": "John Doe",
        "email": "john@example.com",
        "status": "active",
    }
    try:
        await db.create(new_user, "Users")
        print("✓ User created successfully")
    except Exception as e:
        print(f"✗ Error creating user: {e}")

    # 2. GET ONE - Retrieve a single item
    print("\n2. Getting user...")
    try:
        user = await db.get_one("user-123", "Users")
        print(f"✓ User retrieved: {user}")
    except Exception as e:
        print(f"✗ Error getting user: {e}")

    # 3. UPDATE - Update item attributes
    print("\n3. Updating user status...")
    try:
        update_data = {
            "status": "inactive",
            "lastLogin": 1234567890,
        }
        await db.update_db("user-123", "Users", obj=update_data)
        print("✓ User updated successfully")
    except Exception as e:
        print(f"✗ Error updating user: {e}")

    # 4. QUERY - Query with key condition
    print("\n4. Querying users by email...")
    try:
        results = await db.query(
            table="Users",
            index_name="email-index",
            key_condition={
                "expression": "email = :email",
                "expressionValues": {":email": "john@example.com"},
            },
        )
        print(f"✓ Query results: {len(results)} items found")
    except Exception as e:
        print(f"✗ Error querying: {e}")

    # 5. SCAN - Scan entire table
    print("\n5. Scanning all users...")
    try:
        all_users = await db.scan("Users")
        print(f"✓ Scan complete: {len(all_users)} total users")
    except Exception as e:
        print(f"✗ Error scanning: {e}")

    # 6. BATCH GET - Get multiple items
    print("\n6. Batch getting users...")
    try:
        keys = [{"id": "user-123"}, {"id": "user-456"}]
        batch_result = await db.batch_get(keys, "Users")
        print(f"✓ Batch get complete")
    except Exception as e:
        print(f"✗ Error in batch get: {e}")

    # 7. TRANSACT WRITE - Multiple operations in transaction
    print("\n7. Executing transaction...")
    try:
        transaction_items = [
            {
                "Put": {
                    "Item": {
                        "id": "user-789",
                        "name": "Jane Smith",
                        "email": "jane@example.com",
                    },
                    "TableName": "Users",
                    "ConditionExpression": "attribute_not_exists(id)",
                }
            },
            {
                "Update": {
                    "Key": {"id": "user-123"},
                    "TableName": "Users",
                    "UpdateExpression": "set loginCount = loginCount + :inc",
                    "ExpressionAttributeValues": {":inc": 1},
                }
            },
        ]
        await db.write_multiple(transaction_items)
        print("✓ Transaction completed successfully")
    except Exception as e:
        print(f"✗ Error in transaction: {e}")

    # 8. DELETE - Remove an item
    print("\n8. Deleting user...")
    try:
        await db.delete_one("user-789", "Users")
        print("✓ User deleted successfully")
    except Exception as e:
        print(f"✗ Error deleting user: {e}")

    # 9. BATCH DELETE - Delete multiple items
    print("\n9. Batch deleting users...")
    try:
        keys_to_delete = [{"id": "user-123"}, {"id": "user-456"}]
        await db.batch_delete(keys_to_delete, "Users")
        print("✓ Batch delete complete")
    except Exception as e:
        print(f"✗ Error in batch delete: {e}")


async def reserved_words_example():
    """
    Demonstrate handling of DynamoDB reserved words.

    The helper automatically uses attribute name aliases for reserved words.
    """
    print("\n=== Reserved Words Handling ===")

    try:
        # Update with reserved word attributes
        # 'status', 'name', 'date' are all DynamoDB reserved words
        update_data = {
            "status": "active",
            "name": "Updated Name",
            "date": "2024-03-15",
            "customField": "value",  # Not a reserved word
        }

        result = db.create_update_expression(update_data)
        print("Update expression generated:")
        print(f"  Expression: {result['updateExpression']}")
        print(f"  Values: {result['expressionAttributeValues']}")
        print(f"  Names: {result['expressionAttributeNames']}")

    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    print("=== DynamoDB Helper Usage Examples ===\n")
    print("Note: These examples require proper AWS credentials and existing tables.")
    print("Modify table names and operations for your specific use case.\n")

    asyncio.run(example_usage())
    asyncio.run(reserved_words_example())
