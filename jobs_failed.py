#!/usr/bin/env python3
"""
CRDB Backup Resume Failed Query Script

A Python tool to query Chronosphere for jobs_backup_resume_failed metrics.

This script queries the specified metric and displays:
- Cluster name
- Cluster node (instance)
- Count of failed backup resume jobs
- Earliest timestamp when failures occurred per node

Usage:
    $ python backup_resume_failed_query.py
    $ python backup_resume_failed_query.py --export-json
    $ python backup_resume_failed_query.py --export-json backup_failures.json

Requirements:
    - requests>=2.25.0
    - ddop (1Password integration)

Author: Core Infrastructure Storage CRDB Team
"""

import argparse
import json
from urllib.parse import quote
from datetime import datetime

import requests
from ddop import DDOP

# Get Chronosphere token from 1Password
op = DDOP()

try:
    TOKEN = op.get_item(uuid="chronosphere", fields=["credential"])["credential"]
    if TOKEN is None:
        raise ValueError("Chronosphere credential not found in 1Password")
except ValueError as e:
    print(f"Error: Failed to fetch Chronosphere token: {e}")
    raise EnvironmentError("Failed to retrieve Chronosphere token from 1Password")

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# ANSI color codes
class Colors:
    """ANSI color codes for terminal output formatting."""
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def query_backup_resume_failed():
    """
    Query Chronosphere for jobs_backup_resume_failed metrics over time range.

    Queries the Chronosphere API using a range query to fetch backup resume failure metrics
    for the specified account, cluster, and job over the last 7 days.

    Returns:
        list: List of metric dictionaries containing metric data and time series values.
              Each result contains 'metric' dict with labels and 'values' with [[timestamp, value], ...].
              Returns empty list if no metrics found or on API error.

    Raises:
        None: Errors are caught and printed to console, function returns empty list.
    """
    base_url = "https://doordash.chronosphere.io/data/metrics/api/v1/query_range"

    # The query you specified with time range to get historical data
    query = 'jobs_backup_resume_failed{account_id="611706558220",cluster="selection_growth_prod",job="crdb"}'

    # Query parameters for range query (last 7 days with 1 hour step)
    params = {
        'query': query,
        'start': str(int((datetime.now().timestamp() - 7*24*3600))),  # 7 days ago
        'end': str(int(datetime.now().timestamp())),  # now
        'step': '3600'  # 1 hour step
    }

    try:
        response = requests.get(base_url, headers=headers, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()
            results = data['data']['result']
            return results
        else:
            print(f"Error {response.status_code}: {response.text[:200]}")

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")

    return []

def find_earliest_failures_per_node(results):
    """
    Process time series data to find the earliest failure timestamp per node and current failure count.

    Args:
        results (list): List of metric results from Chronosphere API with time series data

    Returns:
        dict: Dictionary with node instances as keys and earliest failure info as values
    """
    node_earliest_failures = {}

    for result in results:
        metric = result.get('metric', {})
        values = result.get('values', [])

        # Extract node information
        cluster_name = metric.get('cluster', 'Unknown')
        exported_node_id = metric.get('exported_node_id', metric.get('instance', 'Unknown'))
        account_id = metric.get('account_id', 'Unknown')

        # Find earliest non-zero failure and get the latest/current value
        earliest_failure = None
        current_failure_count = 0
        latest_timestamp = 0

        for timestamp, count in values:
            count_value = float(count)
            timestamp_value = float(timestamp)

            # Track the latest value (most recent timestamp)
            if timestamp_value > latest_timestamp:
                latest_timestamp = timestamp_value
                current_failure_count = count_value

            # Find earliest failure (first time count > 0)
            if count_value > 0 and (earliest_failure is None or timestamp_value < earliest_failure):
                earliest_failure = timestamp_value

        # Store the earliest failure for this node
        if earliest_failure is not None:
            node_key = f"{cluster_name}:{exported_node_id}"
            if node_key not in node_earliest_failures or earliest_failure < node_earliest_failures[node_key]['timestamp']:
                node_earliest_failures[node_key] = {
                    'cluster_name': cluster_name,
                    'exported_node_id': exported_node_id,
                    'account_id': account_id,
                    'timestamp': earliest_failure,
                    'current_failure_count': current_failure_count,
                    'latest_timestamp': latest_timestamp
                }

    return node_earliest_failures

def format_backup_failures(node_failures):
    """
    Format and display earliest backup resume failure metrics per node.

    Args:
        node_failures (dict): Dictionary of earliest failures per node

    Returns:
        None: Prints formatted output to console
    """
    if not node_failures:
        print("No backup resume failure metrics found")
        return

    print(f"Found earliest backup failures on {len(node_failures)} nodes:\n")

    # Sort by timestamp to show oldest failures first
    sorted_failures = sorted(node_failures.values(), key=lambda x: x['timestamp'])

    for i, failure in enumerate(sorted_failures, 1):
        cluster_name = failure['cluster_name']
        exported_node_id = failure['exported_node_id']
        account_id = failure['account_id']
        current_count = failure['current_failure_count']
        timestamp_raw = failure['timestamp']

        # Convert Unix timestamp to human readable format (American standard: mm-dd-yyyy hh:mm:ss)
        try:
            dt = datetime.fromtimestamp(timestamp_raw)
            timestamp = dt.strftime('%m-%d-%Y %H:%M:%S')
        except (ValueError, TypeError):
            timestamp = f"Invalid timestamp: {timestamp_raw}"

        # Color code the count based on value
        if current_count > 0:
            colored_count = f"{Colors.RED}{current_count}{Colors.RESET}"
        else:
            colored_count = f"{Colors.GREEN}{current_count}{Colors.RESET}"

        print(f"{i}. Cluster: {Colors.BLUE}{cluster_name}{Colors.RESET}")
        print(f"   Node ID: {exported_node_id}")
        print(f"   Current Failure Count: {colored_count}")
        print(f"   Account ID: {account_id}")
        print(f"   Earliest Failure Time: {timestamp}")
        print()

def main():
    """
    Main function that orchestrates the backup resume failure query workflow.

    This function performs the following operations:
    1. Parses command-line arguments
    2. Queries Chronosphere for backup resume failure metrics over time
    3. Finds earliest failure timestamp per node
    4. Formats and displays the results
    5. Optionally exports data to JSON file

    Returns:
        None: Function performs side effects (console output, optional file creation)
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Query Chronosphere for backup resume failure metrics (earliest per node)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Display earliest failures per node
  %(prog)s --export-json                     # Display and export to default file
  %(prog)s --export-json backup_data.json   # Display and export to custom file
        """
    )
    parser.add_argument(
        '--export-json',
        nargs='?',
        const='backup_resume_failed_metrics.json',
        metavar='FILENAME',
        help='Export metric data to JSON file (default: backup_resume_failed_metrics.json)'
    )

    args = parser.parse_args()

    print("Querying Chronosphere for backup resume failure metrics (last 7 days)...")
    print("Query: jobs_backup_resume_failed{account_id=\"611706558220\",cluster=\"selection_growth_prod\",job=\"crdb\"}")
    print("Finding earliest failure timestamp per node...\n")

    # Execute query
    results = query_backup_resume_failed()

    # Process to find earliest failures per node
    node_failures = find_earliest_failures_per_node(results)

    # Format and display results
    format_backup_failures(node_failures)

    # Export to JSON if requested
    if args.export_json:
        try:
            with open(args.export_json, 'w', encoding='utf-8') as f:
                json.dump(node_failures, f, indent=2, default=str)
            print(f"Exported earliest failures for {len(node_failures)} nodes to '{args.export_json}'")
        except IOError as e:
            print(f"Error exporting to JSON: {e}")

if __name__ == "__main__":
    main()