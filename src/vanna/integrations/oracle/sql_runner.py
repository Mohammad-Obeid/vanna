"""Oracle implementation of SqlRunner interface."""

from typing import Optional
import os
import pandas as pd

from vanna.capabilities.sql_runner import SqlRunner, RunSqlToolArgs
from vanna.core.tool import ToolContext

# Track if thick mode has been initialized (can only be done once per process)
_thick_mode_initialized = False


def _init_thick_mode_if_needed(oracledb):
    """Initialize Oracle thick mode if needed and not already done.
    
    Thick mode is required for older Oracle database servers that don't
    support the newer thin mode driver. It requires Oracle Instant Client
    to be installed on the system.
    """
    global _thick_mode_initialized
    if _thick_mode_initialized:
        return
    
    # Check if we should use thick mode (can be forced via env var)
    use_thick = os.environ.get("ORACLE_THICK_MODE", "").lower() in ("1", "true", "yes")
    
    # Also check if Oracle Instant Client path is set
    instant_client_path = os.environ.get("ORACLE_INSTANT_CLIENT_PATH", "")
    
    if use_thick or instant_client_path:
        try:
            # Fix ORA-12638 by disabling NTS authentication before init
            # This must be set BEFORE init_oracle_client is called
            os.environ["SQLNET_AUTHENTICATION_SERVICES"] = "NONE"
            
            if instant_client_path:
                oracledb.init_oracle_client(lib_dir=instant_client_path)
            else:
                # Let oracledb find the client automatically from PATH
                oracledb.init_oracle_client()
            _thick_mode_initialized = True
            print("✅ Oracle thick mode initialized successfully")
        except oracledb.ProgrammingError as e:
            if "already initialized" in str(e).lower():
                _thick_mode_initialized = True
            else:
                print(f"⚠️ Failed to initialize Oracle thick mode: {e}")
                raise


class OracleRunner(SqlRunner):
    """Oracle implementation of the SqlRunner interface."""

    def __init__(self, user: str, password: str, dsn: str, thick_mode: bool = True, **kwargs):
        """Initialize with Oracle connection parameters.

        Args:
            user: Oracle database user name
            password: Oracle database user password
            dsn: Oracle database host - format: host:port/sid
            thick_mode: If True, initialize thick mode for older Oracle servers.
                       Requires Oracle Instant Client to be installed.
                       Can also be controlled via ORACLE_THICK_MODE env var.
            **kwargs: Additional oracledb connection parameters
        """
        try:
            import oracledb

            self.oracledb = oracledb
        except ImportError as e:
            raise ImportError(
                "oracledb package is required. Install with: pip install 'vanna[oracle]'"
            ) from e

        # Initialize thick mode if requested (for older Oracle servers)
        if thick_mode or os.environ.get("ORACLE_THICK_MODE", "").lower() in ("1", "true", "yes"):
            try:
                _init_thick_mode_if_needed(oracledb)
            except Exception as e:
                print(f"⚠️ Warning: Could not initialize Oracle thick mode: {e}")
                print("   Your Oracle server version may require 'thick mode'.")
                print("   Please install Oracle Instant Client:")
                print("   1. Download from: https://www.oracle.com/database/technologies/instant-client/downloads.html")
                print("   2. Extract and add to PATH (or set ORACLE_INSTANT_CLIENT_PATH env var)")
                print("   3. Set ORACLE_THICK_MODE=true environment variable")
                print("   4. Restart the backend server")

        self.user = user
        self.password = password
        self.dsn = dsn
        self.kwargs = kwargs

    async def run_sql(self, args: RunSqlToolArgs, context: ToolContext) -> pd.DataFrame:
        """Execute SQL query against Oracle database and return results as DataFrame.

        Args:
            args: SQL query arguments
            context: Tool execution context

        Returns:
            DataFrame with query results

        Raises:
            oracledb.Error: If query execution fails
        """
        # Connect to the database
        conn = self.oracledb.connect(
            user=self.user, password=self.password, dsn=self.dsn, **self.kwargs
        )

        cursor = conn.cursor()

        try:
            # Strip and remove trailing semicolons (Oracle doesn't like them)
            sql = args.sql.rstrip()
            if sql.endswith(";"):
                sql = sql[:-1]

            # Execute the query
            cursor.execute(sql)
            results = cursor.fetchall()

            # Create a pandas dataframe from the results
            df = pd.DataFrame(results, columns=[desc[0] for desc in cursor.description])
            return df

        except self.oracledb.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
