import re
from pathlib import Path
from collections import defaultdict
from jira import JIRA
from onepassword import OnePassword
import argparse



def extract_alerts(filepath):
    yellow = defaultdict(set)
    red = defaultdict(set)
    pattern = re.compile(r"\](.*?)\{")
    cluster_pattern = re.compile(r'cluster="([^"]+)"')

    with open(filepath, "r") as f:
        for line in f:
            if "large_yellow_circle" in line or "large_red_circle" in line:
                match = pattern.search(line)
                cluster_match = cluster_pattern.search(line)
                if match and cluster_match:
                    alert_text = match.group(1).strip()
                    cluster_name = cluster_match.group(1)
                    if "large_yellow_circle" in line:
                        yellow[cluster_name].add(alert_text)
                    else:
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
        'summary': summary + description ,
        'description': description,
        'issuetype': {'name': 'Task'},
        'labels': ['alerts'],
        'parent': {'id': '6790262'}
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
    alerts_path = Path.home() / "Documents" / "ALERTS"
    health_path = Path.home() / "Desktop" / "HEALTH"
    parser = argparse.ArgumentParser(description="Alert scraper and Jira creator")
    parser.add_argument("--dry_run", required=True, choices=["true", "false"], help="If true, do not create Jira issues, just print actions.")

    args = parser.parse_args()
    dry_run = args.dry_run.lower() == "true"
    
    yellow_alerts, red_alerts = extract_alerts(alerts_path)

    # Parse HEALTH file, sort and unique
    health_issues = set()
    if health_path.exists():
        with open(health_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    health_issues.add(line)
    health_issues = sorted(health_issues)

    # Jira setup
    username, password, hostname = get_jira_credentials_from_1password()

    jira = JIRA(
        server=f"https://{hostname}",
        basic_auth=(username, password)
    )
    project_key = "CRDBOP"
    epic_key = "CRDBOP-4281"

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
