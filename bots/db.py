"""
DynamoDB helper module for BizBot.

Python port of the JavaScript database utilities, providing comprehensive
DynamoDB operations using boto3. IAM permissions are provided by the AWS
Lightsail instance role - no credentials needed in code.
"""

from dotenv import load_dotenv

load_dotenv(override=True)

import os
import time
from typing import Optional, Dict, Any, List
import boto3
from botocore.exceptions import ClientError

from .constants import RESERVED_WORDS


class DynamoDBHelper:
    """
    Comprehensive DynamoDB helper class mirroring the JavaScript implementation.
    Provides CRUD operations, batch operations, transactions, and query helpers.
    """

    def __init__(self):
        """Initialize DynamoDB client using IAM role credentials."""
        region = os.getenv("AWS_REGION", "us-west-2")
        self.dynamodb = boto3.resource("dynamodb", region_name=region)  # type: ignore
        self.client = boto3.client("dynamodb", region_name=region)
        self.environment = os.getenv("ENVIRONMENT", "")

    def _get_table(self, table_name: str):
        """Get table resource with environment suffix."""
        full_table_name = f"{table_name}{self.environment}"
        return self.dynamodb.Table(full_table_name)  # type: ignore

    def dynamo_error_response(self, err: Exception) -> Dict[str, Any]:
        """
        Format DynamoDB error into consistent response structure.

        Args:
            err: Exception from DynamoDB operation

        Returns:
            Formatted error response dict
        """
        if isinstance(err, ClientError):
            error_code = err.response.get("Error", {}).get("Code", "Unknown")
            status_code = err.response.get("ResponseMetadata", {}).get(
                "HTTPStatusCode", 502
            )
            message = err.response.get("Error", {}).get("Message", str(err))

            body = {
                "code": error_code,
                "message": message,
                "time": time.time(),
                "statusCode": status_code,
            }
        else:
            body = {
                "message": str(err),
                "time": time.time(),
                "statusCode": 502,
            }
            status_code = 502

        response = {
            "statusCode": status_code,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": True,
            },
            "type": type(err).__name__,
            "body": body,
        }

        print(f"DYNAMO DB ERROR: {err}")
        return response

    def create_update_expression(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create DynamoDB update expression from object.

        Handles reserved words by using attribute name aliases.
        Automatically adds updatedAt timestamp.

        Args:
            obj: Dictionary of attributes to update

        Returns:
            Dict containing updateExpression, expressionAttributeValues,
            and expressionAttributeNames
        """
        val = 0
        update_expression = "set "
        expression_attribute_values = {}
        expression_attribute_names = None

        for key, value in obj.items():
            # Skip primary keys and updatedAt (added automatically)
            if key in ("id", "eventID;year", "updatedAt"):
                continue

            if key.upper() in RESERVED_WORDS:
                # Use attribute name alias for reserved words
                update_expression += f"#v{val} = :val{val},"
                expression_attribute_values[f":val{val}"] = value
                if expression_attribute_names is None:
                    expression_attribute_names = {}
                expression_attribute_names[f"#v{val}"] = key
                val += 1
            else:
                update_expression += f"{key} = :{key},"
                expression_attribute_values[f":{key}"] = value

        # Add timestamp
        timestamp = int(time.time() * 1000)
        update_expression += "updatedAt = :updatedAt"
        expression_attribute_values[":updatedAt"] = timestamp

        return {
            "updateExpression": update_expression,
            "expressionAttributeValues": expression_attribute_values,
            "expressionAttributeNames": expression_attribute_names,
        }

    # DATABASE INTERACTIONS

    async def create(self, item: Dict[str, Any], table: str) -> Dict[str, Any]:
        """
        Create new item in DynamoDB table.

        Uses ConditionExpression to ensure item doesn't already exist.

        Args:
            item: Item dictionary to create
            table: Table name (without environment suffix)

        Returns:
            DynamoDB response

        Raises:
            Exception with formatted error response if operation fails
        """
        try:
            table_resource = self._get_table(table)
            response = table_resource.put_item(
                Item=item, ConditionExpression="attribute_not_exists(id)"
            )
            return response
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)

    async def get_one(
        self, item_id: str, table: str, extra_keys: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get single item from DynamoDB table.

        Args:
            item_id: Primary key id
            table: Table name (without environment suffix)
            extra_keys: Additional keys for composite primary keys

        Returns:
            Item dict if found, None otherwise

        Raises:
            Exception with formatted error response if operation fails
        """
        try:
            table_resource = self._get_table(table)
            key = {"id": item_id}
            if extra_keys:
                key.update(extra_keys)

            response = table_resource.get_item(Key=key)
            return response.get("Item")
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)

    async def get_one_custom(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get item with custom parameters.

        Args:
            params: Full GetItem parameters dict

        Returns:
            Item dict if found, None otherwise

        Raises:
            Exception with formatted error response if operation fails
        """
        try:
            response = self.client.get_item(**params)
            return response.get("Item")
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)

    async def scan(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        index_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scan entire table and return all items.

        Automatically handles pagination to retrieve all items.

        Args:
            table: Table name (without environment suffix)
            filters: Optional scan filters
            index_name: Optional GSI/LSI name

        Returns:
            List of all items in table

        Raises:
            Exception with formatted error response if operation fails
        """
        try:
            table_resource = self._get_table(table)
            scan_kwargs = filters or {}

            if index_name:
                scan_kwargs["IndexName"] = index_name

            items = []
            last_evaluated_key = None

            while True:
                if last_evaluated_key:
                    scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

                response = table_resource.scan(**scan_kwargs)
                items.extend(response.get("Items", []))

                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break

            return items
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)

    async def batch_get(
        self, batch: List[Dict[str, Any]], table_name: str
    ) -> Dict[str, Any]:
        """
        Batch get items from table.

        Args:
            batch: List of key dictionaries
            table_name: Table name (without environment suffix)

        Returns:
            BatchGetItem response

        Raises:
            Exception with formatted error response if operation fails
        """
        try:
            full_table_name = f"{table_name}{self.environment}"
            batch_request_params = {"RequestItems": {full_table_name: {"Keys": batch}}}

            print(f"BatchRequestParams: {batch_request_params}")
            response = self.client.batch_get_item(**batch_request_params)
            return response
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)

    async def batch_delete(
        self, items: List[Dict[str, Any]], table_name: str
    ) -> Dict[str, Any]:
        """
        Batch delete items from table.

        Args:
            items: List of key dictionaries to delete
            table_name: Table name (without environment suffix)

        Returns:
            BatchWriteItem response

        Raises:
            Exception with formatted error response if operation fails
        """
        try:
            full_table_name = f"{table_name}{self.environment}"
            delete_requests = [{"DeleteRequest": {"Key": key}} for key in items]

            batch_request_params = {"RequestItems": {full_table_name: delete_requests}}

            response = self.client.batch_write_item(**batch_request_params)
            return response
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)

    async def delete_one(
        self, item_id: str, table: str, extra_keys: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Delete single item from table.

        Args:
            item_id: Primary key id
            table: Table name (without environment suffix)
            extra_keys: Additional keys for composite primary keys

        Returns:
            DeleteItem response

        Raises:
            Exception with formatted error response if operation fails
        """
        try:
            table_resource = self._get_table(table)
            key = {"id": item_id}
            if extra_keys:
                key.update(extra_keys)

            response = table_resource.delete_item(Key=key)
            return response
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)

    async def update_db(
        self,
        key: str | Dict[str, Any],
        table: str,
        obj: Optional[Dict[str, Any]] = None,
        update_expression: Optional[str] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        condition_expression: Optional[str] = None,
        return_values: str = "UPDATED_NEW",
    ) -> Dict[str, Any]:
        """
        Update item in table.

        Two modes of operation:
        1. Auto-generate (simple): Pass `obj` dict, UpdateExpression is auto-generated.
           Automatically handles reserved words and adds updatedAt timestamp.
        2. Manual (advanced): Pass custom `update_expression` with explicit values/names.
           Use this for complex operations like conditional updates, ADD, REMOVE, etc.

        Args:
            key: Primary key - string for simple {"id": key} or dict for composite keys
            table: Table name (without environment suffix)
            obj: Dictionary of attributes to update (auto-generates expression).
                 Mutually exclusive with update_expression.
            update_expression: Custom UpdateExpression string.
                              Mutually exclusive with obj.
            expression_attribute_values: Values for placeholders in expressions
            expression_attribute_names: Names for attribute aliases (reserved words)
            condition_expression: ConditionExpression for the update.
                                  - Auto mode: defaults to checking key existence
                                  - Manual mode: required (pass None explicitly to disable)
            return_values: What to return (default: UPDATED_NEW)

        Returns:
            UpdateItem response

        Raises:
            ValueError if both obj and update_expression are provided
            Exception with formatted error response if operation fails
        """
        # Validate mutual exclusivity
        if obj and update_expression:
            raise ValueError("Cannot specify both 'obj' and 'update_expression'")
        if not obj and not update_expression:
            raise ValueError("Must specify either 'obj' or 'update_expression'")

        # Convert string key to dict for backward compatibility
        if isinstance(key, str):
            key_dict = {"id": key}
        else:
            key_dict = key

        try:
            table_resource = self._get_table(table)

            if obj:
                # Auto-generate mode
                update_expr = self.create_update_expression(obj)
                final_expression = update_expr["updateExpression"]
                final_values = update_expr["expressionAttributeValues"]
                final_names = update_expr.get("expressionAttributeNames")

                # Default condition: check first key exists
                if condition_expression is None:
                    first_key = next(iter(key_dict.keys()))
                    condition_expression = f"attribute_exists({first_key})"
            else:
                # Manual mode
                final_expression = update_expression
                final_values = expression_attribute_values or {}
                final_names = expression_attribute_names

            update_kwargs: Dict[str, Any] = {
                "Key": key_dict,
                "UpdateExpression": final_expression,
                "ReturnValues": return_values,
            }

            if final_values:
                update_kwargs["ExpressionAttributeValues"] = final_values

            if final_names:
                update_kwargs["ExpressionAttributeNames"] = final_names

            if condition_expression:
                update_kwargs["ConditionExpression"] = condition_expression

            response = table_resource.update_item(**update_kwargs)
            return response
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)

    async def update_db_custom(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update item with custom parameters.

        Args:
            params: Full UpdateItem parameters dict

        Returns:
            UpdateItem response

        Raises:
            Exception with formatted error response if operation fails
        """
        try:
            response = self.client.update_item(**params)
            return response
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)

    async def put(
        self, obj: Dict[str, Any], table: str, create_new: bool = False
    ) -> Dict[str, Any]:
        """
        Put item into table (create or replace).

        Args:
            obj: Item to put
            table: Table name (without environment suffix)
            create_new: If True, only create new items; if False, only update existing

        Returns:
            PutItem response

        Raises:
            Exception with formatted error response if operation fails
        """
        try:
            table_resource = self._get_table(table)
            condition_expression = (
                "attribute_not_exists(id)" if create_new else "attribute_exists(id)"
            )

            response = table_resource.put_item(
                Item=obj, ConditionExpression=condition_expression
            )
            return response
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)

    async def put_multiple(
        self, items: List[Dict[str, Any]], tables: List[str], create_new: bool = False
    ) -> Dict[str, Any]:
        """
        Put multiple items in a transaction.

        Args:
            items: List of items to put
            tables: List of table names (must match items length)
            create_new: If True, only create new items; if False, only update existing

        Returns:
            TransactWriteItems response

        Raises:
            Exception if items and tables lengths don't match or exceed 25 items
            Exception with formatted error response if operation fails
        """
        try:
            if len(items) != len(tables):
                raise Exception(
                    {
                        "statusCode": 502,
                        "headers": {
                            "Access-Control-Allow-Origin": "*",
                            "Access-Control-Allow-Credentials": True,
                        },
                        "type": "Transaction items does not match length of tables to write",
                        "body": {"items": items, "tables": tables},
                    }
                )

            if len(items) > 25 or len(items) == 0:
                raise Exception(
                    {
                        "statusCode": 502,
                        "headers": {
                            "Access-Control-Allow-Origin": "*",
                            "Access-Control-Allow-Credentials": True,
                        },
                        "type": "Cannot exceed greater than 25 transaction items, or have an empty transaction",
                        "body": {"items": items, "tables": tables},
                    }
                )

            condition_expression = (
                "attribute_not_exists(id)" if create_new else "attribute_exists(id)"
            )

            transact_items = []
            for obj, table in zip(items, tables):
                full_table_name = f"{table}{self.environment}"
                transact_items.append(
                    {
                        "Put": {
                            "Item": obj,
                            "TableName": full_table_name,
                            "ConditionExpression": condition_expression,
                        }
                    }
                )

            response = self.client.transact_write_items(TransactItems=transact_items)
            return response
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)

    async def write_multiple(
        self, transact_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute multiple write operations in a transaction.

        Supports Put, Update, Delete, and ConditionCheck operations.

        Args:
            transact_items: List of transaction item dicts (Put/Update/Delete/ConditionCheck)

        Returns:
            TransactWriteItems response

        Raises:
            Exception if item count is invalid (0 or >25)
            Exception with formatted error response if operation fails
        """
        try:
            if (
                not transact_items
                or len(transact_items) == 0
                or len(transact_items) > 25
            ):
                raise Exception(
                    {
                        "statusCode": 502,
                        "headers": {
                            "Access-Control-Allow-Origin": "*",
                            "Access-Control-Allow-Credentials": True,
                        },
                        "type": "Cannot exceed greater than 25 transaction items, or have an empty transaction",
                        "body": {"transactItems": transact_items},
                    }
                )

            table_suffix = self.environment

            # Add environment suffix to all table names
            items_with_env = []
            for item in transact_items:
                new_item = {}

                if "Put" in item:
                    put_item = item["Put"].copy()
                    put_item["TableName"] = f"{item['Put']['TableName']}{table_suffix}"
                    new_item["Put"] = put_item
                elif "Update" in item:
                    update_item = item["Update"].copy()
                    update_item["TableName"] = (
                        f"{item['Update']['TableName']}{table_suffix}"
                    )
                    new_item["Update"] = update_item
                elif "Delete" in item:
                    delete_item = item["Delete"].copy()
                    delete_item["TableName"] = (
                        f"{item['Delete']['TableName']}{table_suffix}"
                    )
                    new_item["Delete"] = delete_item
                elif "ConditionCheck" in item:
                    condition_item = item["ConditionCheck"].copy()
                    condition_item["TableName"] = (
                        f"{item['ConditionCheck']['TableName']}{table_suffix}"
                    )
                    new_item["ConditionCheck"] = condition_item
                else:
                    new_item = item

                items_with_env.append(new_item)

            response = self.client.transact_write_items(TransactItems=items_with_env)
            return response
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)

    async def query(
        self,
        table: str,
        index_name: Optional[str],
        key_condition: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query table with key condition.

        Args:
            table: Table name (without environment suffix)
            index_name: Optional GSI/LSI name
            key_condition: Dict with 'expression', 'expressionValues', and optional 'expressionNames'
            filters: Optional dict with FilterExpression, ExpressionAttributeValues, etc.

        Returns:
            List of items matching query

        Raises:
            Exception with formatted error response if operation fails

        Example:
            items = await db.query(
                table="Users",
                index_name="email-index",
                key_condition={
                    "expression": "email = :email",
                    "expressionValues": {":email": "user@example.com"}
                }
            )
        """
        try:
            table_resource = self._get_table(table)
            filters = filters or {}

            query_kwargs = {
                "KeyConditionExpression": key_condition["expression"],
                "ExpressionAttributeValues": {
                    **key_condition.get("expressionValues", {}),
                    **filters.get("ExpressionAttributeValues", {}),
                },
            }

            # Merge expression attribute names
            key_names = key_condition.get("expressionNames", {})
            filter_names = filters.get("ExpressionAttributeNames", {})
            if key_names or filter_names:
                query_kwargs["ExpressionAttributeNames"] = {**key_names, **filter_names}

            if "FilterExpression" in filters:
                query_kwargs["FilterExpression"] = filters["FilterExpression"]

            if index_name:
                query_kwargs["IndexName"] = index_name

            response = table_resource.query(**query_kwargs)

            if not response:
                print("Query returned no result")
                return []

            return response.get("Items", [])
        except Exception as err:
            error_response = self.dynamo_error_response(err)
            raise Exception(error_response)


# Global instance (singleton)
db = DynamoDBHelper()
