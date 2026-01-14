"""
Quick Azure SQL Connection Test
Run this locally to verify your Azure SQL connection works
"""

from dotenv import load_dotenv
load_dotenv()  # Load .env file

from azure_db import test_connection
import sys

def main():
    print("=" * 60)
    print("Azure SQL Connection Test")
    print("=" * 60)

    result = test_connection()

    print(f"\nTest Results:")
    print(f"  Connection Mode: {result['mode']}")
    print(f"  Azure Configured: {result['azure_configured']}")
    print(f"  pyodbc Available: {result['pyodbc_available']}")
    print(f"  Connection Test: {result['connection_test']}")

    if result['row_count']:
        print(f"  Row Count: {result['row_count']:,}")

    if result['error']:
        print(f"\nERROR Details:")
        print(f"  {result['error']}")
        print(f"\nTroubleshooting:")
        print(f"  1. Check if Azure SQL database is 'Online' in Azure Portal")
        print(f"  2. Verify firewall rule 0.0.0.0-255.255.255.255 exists")
        print(f"  3. If database is 'Paused', click 'Resume' and wait 1 minute")
        print(f"  4. Verify connection string password is correct in .env")
        sys.exit(1)
    else:
        print(f"\nSUCCESS: Connection successful!")
        print(f"  Database is online with {result['row_count']:,} rows")
        sys.exit(0)

if __name__ == "__main__":
    main()
