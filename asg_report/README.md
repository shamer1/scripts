# ASG Report Tool

A comprehensive Python script for analyzing AWS Auto Scaling Groups (ASGs) and EC2 instances based on the `crdb_cluster_name` tag. This tool provides detailed reporting on instance configurations, launch template versions, AMI IDs, availability zone distribution, and ASG lifecycle states.

## Features

- **Instance Discovery**: Find all EC2 instances tagged with a specific `crdb_cluster_name`
- **ASG Integration**: Correlate instances with their Auto Scaling Groups
- **Comprehensive Reporting**: Detailed tables showing instance details, summaries by AZ, launch template versions, and more
- **Multi-Region Support**: Query instances across different AWS regions
- **Profile Support**: Use different AWS profiles for access
- **Debug Mode**: Verbose output for troubleshooting
- **Output Options**: Save reports to file or display in terminal
- **Cluster Discovery**: List all available CRDB clusters in a region

## Prerequisites

- Python 3.6+
- AWS CLI configured with appropriate credentials
- Required Python packages:
  ```bash
  pip install boto3
  ```

## Installation

1. Clone this repository or download the script
2. Ensure AWS credentials are configured via:
   - AWS CLI (`aws configure`)
   - Environment variables
   - IAM roles (for EC2 instances)
   - AWS profiles

## Usage

### Basic Commands

#### List Available CRDB Clusters
```bash
python3 asg_report.py --list-clusters
```

#### Generate Report for a Specific Cluster
```bash
python3 asg_report.py --crdb-cluster-name merchant_financial-svc_prod
```

#### Use Specific AWS Profile and Region
```bash
python3 asg_report.py --profile production --region us-west-2 --crdb-cluster-name merchant_financial-svc_prod
```

#### Enable Debug Output
```bash
python3 asg_report.py --crdb-cluster-name merchant_financial-svc_prod --debug
```

#### Save Report to File
```bash
python3 asg_report.py --crdb-cluster-name merchant_financial-svc_prod --output cluster_report.txt
```

### Command Line Options

| Option | Description | Required |
|--------|-------------|----------|
| `--crdb-cluster-name` | Name of the CRDB cluster to analyze | Yes (unless using `--list-clusters`) |
| `--list-clusters` | List all available CRDB cluster names and exit | No |
| `--profile` | AWS profile to use | No |
| `--region` | AWS region to query (defaults to profile's default region) | No |
| `--debug` | Enable verbose debug output | No |
| `--output` | Output file path (defaults to stdout) | No |

## Output Format

The tool generates a comprehensive report with the following sections:

### 1. Header Information
- Cluster name being analyzed
- AWS region
- Total number of instances found
- Report generation timestamp

### 2. Instance Details Table
Detailed table showing:
- Instance ID
- Auto Scaling Group name
- ASG lifecycle state
- Launch template version
- AMI ID
- Instance type
- Instance state
- Availability zone

### 3. Summary Sections
- **Auto Scaling Group Summary**: Instance count per ASG
- **Availability Zone Summary**: Instance distribution across AZs
- **Launch Template Version Summary**: Version distribution
- **Instance State Summary**: State distribution (running, stopped, etc.)
- **ASG Lifecycle State Summary**: ASG lifecycle state distribution

## Example Output

Here's an example of the tool's output for a production cluster:

```
====================================================================================================================================================================================
INSTANCE REPORT FOR CRDB CLUSTER: merchant_financial-svc_prod
Region: us-west-2
Total Instances Found: 91
Generated: 2025-07-30 08:53:37
====================================================================================================================================================================================

INSTANCE DETAILS:
Instance ID          ASG Name                                                ASG State       LT Ver   AMI ID                Type            State        AZ             
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
i-00cec71ae3e51686b  merchant_financial-svc_prod-20210420180424245200000013  InService       75       ami-010e5df62ced96f07 m7g.8xlarge     running      us-west-2a     
i-012e462796173ffc4  merchant_financial-svc_prod-20210420180424245200000013  InService       75       ami-010e5df62ced96f07 m7g.8xlarge     running      us-west-2a     
...

======================================== AUTO SCALING GROUP SUMMARY ========================================
ASG Name                                                     Instance Count 
---------------------------------------------------------------------------
merchant_financial-svc_prod-20210420180424245200000013       91             

======================================== AVAILABILITY ZONE SUMMARY ========================================
Availability Zone    Instance Count 
-----------------------------------
us-west-2a           30             
us-west-2b           31             
us-west-2c           30             

======================================== LAUNCH TEMPLATE VERSION SUMMARY ===================================
Template Version     Instance Count 
-----------------------------------
75                   71             
78                   1              
79                   19             

======================================== INSTANCE STATE SUMMARY ========================================
State                Instance Count 
-----------------------------------
running              91             

======================================== ASG LIFECYCLE STATE SUMMARY ===================================
Lifecycle State      Instance Count 
-----------------------------------
InService            91             
```

### Output Analysis Summary

This example output shows:

- **Cluster Scale**: 91 total instances in the `merchant_financial-svc_prod` cluster
- **Geographic Distribution**: Well-balanced across 3 availability zones (30-31 instances each)
- **Launch Template Versions**: Mix of versions with majority on v75 (71 instances), some on newer v79 (19 instances), and one on v78
- **Operational State**: All instances are running and in service
- **Single ASG**: All instances belong to one Auto Scaling Group
- **Instance Type**: Consistent m7g.8xlarge instances across the cluster
- **High Availability**: Even distribution across us-west-2a, us-west-2b, and us-west-2c

This type of report is valuable for:
- **Capacity Planning**: Understanding current scale and distribution
- **Version Management**: Tracking launch template version rollouts
- **Health Monitoring**: Identifying instances not in desired states
- **Availability Analysis**: Ensuring proper multi-AZ distribution
- **Compliance Checking**: Verifying configuration consistency

## AWS Permissions Required

The script requires the following AWS IAM permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "autoscaling:DescribeAutoScalingGroups"
            ],
            "Resource": "*"
        }
    ]
}
```

## Troubleshooting

### Common Issues

1. **No instances found**: Verify the cluster name and ensure instances have the `crdb_cluster_name` tag
2. **Permission denied**: Check AWS credentials and IAM permissions
3. **Region issues**: Specify the correct region using `--region` parameter
4. **Profile issues**: Verify AWS profile exists and is correctly configured

### Debug Mode

Use the `--debug` flag for verbose output that shows:
- Session configuration details
- Instance discovery progress
- ASG mapping information
- Launch template details

### Example Debug Output
```bash
python3 asg_report.py --crdb-cluster-name test-cluster --debug
```

This will show detailed information about the discovery process and help identify issues.

## Use Cases

- **Infrastructure Auditing**: Regular reports on cluster composition
- **Deployment Tracking**: Monitor launch template version rollouts
- **Capacity Planning**: Understand current scale and distribution
- **Troubleshooting**: Identify misplaced or misconfigured instances
- **Compliance**: Ensure proper tagging and configuration standards

## Contributing

Feel free to submit issues and enhancement requests. Pull requests are welcome for bug fixes and new features.
