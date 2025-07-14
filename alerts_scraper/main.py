import re
from pathlib import Path
from collections import defaultdict
from jira import JIRA
from onepassword import OnePassword



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
        'summary': summary,
        'description': description,
        'issuetype': {'name': 'Task'},
        'labels': ['alerts'],
        'parent': {'id': '6790262'}
    }
    return jira.create_issue(fields=issue_dict)




if __name__ == "__main__":
    alerts_path = Path.home() / "Documents" / "ALERTS"
    yellow_alerts, red_alerts = extract_alerts(alerts_path)

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
            summary = f"Yellow Alert for {cluster}"
            description = alert
            issue = create_jira_issue(jira, project_key, summary, description, epic_key)
            print(f"Created Jira issue {issue.key} for cluster {cluster}: {alert}")

    for cluster, alerts in red_alerts.items():
        for alert in alerts:
            summary = f"Red Alert for {cluster}"
            description = alert
            issue = create_jira_issue(jira, project_key, summary, description, epic_key)
            print(f"Created Jira issue {issue.key} for cluster {cluster}: {alert}")