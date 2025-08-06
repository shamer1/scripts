import re
from pathlib import Path
from collections import defaultdict
from jira import JIRA
from onepassword import OnePassword
import argparse
import sys


def extract_alerts(filepath):
    yellow = defaultdict(set)
    red = defaultdict(set)
    pattern = re.compile(r"\](.*?)\{")
    cluster_pattern = re.compile(r'cluster="([^"]+)"')

    yellow_keys = [":large_yellow_circle:", ":yellow_circle:", "large_yellow_circle"]
    red_keys = [":large_red_circle:", ":red_circle:", "large_red_circle"]

    with open(filepath, "r") as f:
        for line in f:
            # Check for yellow or red event
            is_yellow = any(key in line for key in yellow_keys)
            is_red = any(key in line for key in red_keys)
            if is_yellow or is_red:
                match = pattern.search(line)
                cluster_match = cluster_pattern.search(line)
                if match and cluster_match:
                    alert_text = match.group(1).strip()
                    cluster_name = cluster_match.group(1)
                    if is_yellow:
                        yellow[cluster_name].add(alert_text)
                    elif is_red:
                        red[cluster_name].add(alert_text)
    return yellow, red


def get_jira_credentials_from_1password():
    """
    Fetch Jira credentials and hostname from 1Password using the onepassword Python package.
    Expects fields: username, credential, hostname.
    """
    try:
        op = OnePassword()
        item = op.get_item("jira")
        # Adjust this if your onepassword package returns a different structure
        fields = {f['label']: f.get('value', '') for f in item.get('fields', [])}
        username = fields.get('username')
        password = fields.get('credential')
        hostname = fields.get('hostname')
        if not all([username, password, hostname]):
            print("Missing username, credential, or hostname in 1Password item 'jira'.")
            sys.exit(1)
        # Remove protocol from hostname if present
        hostname = hostname.replace("https://", "").replace("http://", "")
        return username, password, hostname
    except Exception as e:
        print(f"Error fetching Jira credentials from 1Password: {e}")
        sys.exit(1)

def create_jira_issue(jira, project_key, summary, description, epic_key):
    issue_dict = {
        'project': {'key': project_key},
        'summary': summary + description,
        'description': description,
        'issuetype': {'name': 'Task'},
        'labels': ['alerts'],
        'parent': {'key': epic_key}  # Use the epic_key parameter instead of hardcoded ID
    }
    return jira.create_issue(fields=issue_dict)


def search_existing_jira_issues(jira, project_key, summary, days=30):
    """
    Search for existing Jira issues in the given project with the given summary in the last N days.
    Returns a list of matching issues.
    """
    from datetime import datetime, timedelta
    since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    # Jira JQL: project = CRDBOP AND summary ~ "Alert for cluster" AND created >= -30d
    jql = f'project = {project_key} AND summary ~ "{summary}" AND created >= "{since}"'
    try:
        issues = jira.search_issues(jql)
        return issues
    except Exception as e:
        print(f"Error searching Jira: {e}")
        return []




if __name__ == "__main__":

    alerts_path = Path.home() / "Desktop" / "ALERTS"
    health_path = Path.home() / "Desktop" / "HEALTH"
    parser = argparse.ArgumentParser(description="Alert scraper and Jira creator")
    parser.add_argument("--dry_run", required=True, choices=["true", "false"], help="If true, do not create Jira issues, just print actions.")
    parser.add_argument("-e", "--epic", required=True, help="Epic key for linking Jira issues (e.g., CRDBOP-4281)")

    args = parser.parse_args()
    dry_run = args.dry_run.lower() == "true"
    epic_key = args.epic

    # --- Reporting: ALERTS file line count ---
    alerts_line_count = 0
    with open(alerts_path, "r") as f:
        alerts_lines = f.readlines()
        alerts_line_count = len(alerts_lines)
    print(f"[REPORT] ALERTS file contains {alerts_line_count} lines.")

    # --- Reporting: Count yellow/red events before unique/sort ---
    yellow_count_raw = 0
    red_count_raw = 0
    yellow_keys = [":large_yellow_circle:", ":yellow_circle:", "large_yellow_circle"]
    red_keys = [":large_red_circle:", ":red_circle:", "large_red_circle"]
    for line in alerts_lines:
        if any(key in line for key in yellow_keys):
            yellow_count_raw += 1
        if any(key in line for key in red_keys):
            red_count_raw += 1
    print(f"[REPORT] ALERTS file yellow events (raw): {yellow_count_raw}")
    print(f"[REPORT] ALERTS file red events (raw): {red_count_raw}")

    yellow_alerts, red_alerts = extract_alerts(alerts_path)

    # --- Reporting: Count yellow/red events after unique/sort ---
    yellow_count_unique = sum(len(alerts) for alerts in yellow_alerts.values())
    red_count_unique = sum(len(alerts) for alerts in red_alerts.values())
    print(f"[REPORT] ALERTS file yellow events (unique): {yellow_count_unique}")
    print(f"[REPORT] ALERTS file red events (unique): {red_count_unique}")

    # --- Reporting: HEALTH file line count and unique count ---
    health_line_count = 0
    health_issues = set()
    if health_path.exists():
        with open(health_path, "r") as f:
            health_lines = f.readlines()
            health_line_count = len(health_lines)
            for line in health_lines:
                line = line.strip()
                if line:
                    health_issues.add(line)
    print(f"[REPORT] HEALTH file contains {health_line_count} lines.")
    print(f"[REPORT] HEALTH file unique issues: {len(health_issues)}")
    health_issues = sorted(health_issues)

    # Jira setup
    username, password, hostname = get_jira_credentials_from_1password()

    jira = JIRA(
        server=f"https://{hostname}",
        basic_auth=(username, password)
    )
    project_key = "CRDBOP"

    for cluster, alerts in yellow_alerts.items():
        for alert in alerts:
            summary = f"Alert for {cluster} : "
            description = alert
            existing_issues = search_existing_jira_issues(jira, project_key, summary.strip(), days=30)
            found = False
            for issue in existing_issues:
                # Check if alert text is in summary or description
                if alert in issue.fields.summary or alert in getattr(issue.fields, 'description', ''):
                    print(f"EXISTS: Jira issue {issue.key} for cluster {cluster}: {alert}")
                    found = True
            if not found:
                if dry_run == False:
                    issue = create_jira_issue(jira, project_key, summary, description, epic_key)
                    print(f"CREATED: Jira issue {issue.key} for cluster {cluster}: {alert}")
                else:
                    print(f"DRY RUN MODE, WOULD CREATE: Jira issue for cluster {cluster}: {alert}")

    for cluster, alerts in red_alerts.items():
        for alert in alerts:
            summary = f"Red Alert for {cluster}"
            description = alert
            existing_issues = search_existing_jira_issues(jira, project_key, summary.strip(), days=30)
            found = False
            for issue in existing_issues:
                if alert in issue.fields.summary or alert in getattr(issue.fields, 'description', ''):
                    print(f"EXISTS: Jira issue {issue.key} for cluster {cluster}: {alert}")
                    found = True
            if not found:
                if dry_run == False:
                    issue = create_jira_issue(jira, project_key, summary, description, epic_key)
                    print(f"CREATED: Jira issue {issue.key} for cluster {cluster}: {alert}")
                else:
                    print(f"DRY RUN MODE, WOULD CREATE: Jira issue for cluster {cluster}: {alert}")

    # Process HEALTH issues
    for health_issue in health_issues:
        summary = f"HEALTH: {health_issue}"
        description = health_issue
        existing_issues = search_existing_jira_issues(jira, project_key, summary.strip(), days=30)
        found = False
        for issue in existing_issues:
            if health_issue in issue.fields.summary or health_issue in getattr(issue.fields, 'description', ''):
                print(f"EXISTS: Jira issue {issue.key} for HEALTH: {health_issue}")
                found = True
        if not found:
            if dry_run == False:
                issue = create_jira_issue(jira, project_key, summary, description, epic_key)
                print(f"CREATED: Jira issue {issue.key} for HEALTH: {health_issue}")
            else:
                print(f"DRY RUN MODE, WOULD CREATE: Jira issue for HEALTH: {health_issue}")
