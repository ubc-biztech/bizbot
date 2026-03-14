"""
DynamoDB helper module for BizBot.

Uses boto3 to interact with DynamoDB. IAM permissions are provided
by the AWS Lightsail instance role - no credentials needed in code.
"""

import os
import boto3
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError


class DynamoDBClient:
    """Wrapper for DynamoDB operations."""
    
    def __init__(self):
        """Initialize DynamoDB client using IAM role credentials."""
        region = os.getenv("AWS_REGION", "us-east-1")
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table_name = os.getenv("DYNAMODB_TABLE_NAME", "bizbot-tickets")
        self.table = self.dynamodb.Table(self.table_name)
    
    async def get_item(self, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get an item from DynamoDB table.
        
        Args:
            key: Primary key dict (e.g., {"ticket_id": "12345"})
        
        Returns:
            Item dict if found, None otherwise
        
        Example:
            item = await db.get_item({"ticket_id": "test-123"})
        """
        try:
            response = self.table.get_item(Key=key)
            return response.get("Item")
        except ClientError as e:
            print(f"Error fetching item from DynamoDB: {e}")
            return None
    
    async def put_item(self, item: Dict[str, Any]) -> bool:
        """
        Put an item into DynamoDB table.
        
        Args:
            item: Item dict to store
        
        Returns:
            True if successful, False otherwise
        
        Example:
            success = await db.put_item({
                "ticket_id": "test-123",
                "status": "OPEN",
                "description": "Need help with API"
            })
        """
        try:
            self.table.put_item(Item=item)
            return True
        except ClientError as e:
            print(f"Error putting item to DynamoDB: {e}")
            return False
    
    async def scan_table(self, limit: int = 10) -> list:
        """
        Scan table and return items (for testing purposes).
        
        Args:
            limit: Maximum number of items to return
        
        Returns:
            List of items
        
        Example:
            items = await db.scan_table(limit=5)
        """
        try:
            response = self.table.scan(Limit=limit)
            return response.get("Items", [])
        except ClientError as e:
            print(f"Error scanning DynamoDB table: {e}")
            return []


# Global instance (initialized once)
db_client = DynamoDBClient()
