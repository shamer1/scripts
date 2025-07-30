# Changelog

All notable changes to the ASG Report Tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-07-30

### Added
- Private IPv4 address column in instance details table
- Enhanced network troubleshooting capabilities with direct IP access
- Updated table formatting to accommodate new column (increased width from 180 to 200 characters)

### Changed
- Instance details table now displays private IP addresses between "State" and "AZ" columns
- Updated script documentation and usage examples to reflect correct script name (`asg_report.py`)
- Enhanced tool description to mention private IP address reporting
- Improved README.md with comprehensive usage examples and private IP information

### Technical Details
- Added `private_ip` field extraction from EC2 instance data using `instance.get('PrivateIpAddress', 'N/A')`
- Updated `extract_instance_info()` function to include private IP in returned dictionary
- Modified output formatting in `analyze_instances()` function to display private IP column
- Table header format: `Instance ID | ASG Name | ASG State | LT Ver | AMI ID | Type | State | Private IP | AZ`

## [1.0.0] - 2025-07-30

### Added
- Initial release of ASG Report Tool
- EC2 instance discovery by `crdb_cluster_name` tag
- Auto Scaling Group integration and correlation
- Comprehensive reporting with multiple summary sections:
  - Instance details table
  - Auto Scaling Group summary
  - Availability Zone distribution
  - Launch template version analysis
  - Instance state summary
  - ASG lifecycle state summary
- Multi-region and multi-profile AWS support
- Debug mode for troubleshooting
- Output to file capability
- Cluster discovery functionality (`--list-clusters`)
- Command-line interface with argparse
- Complete documentation and usage examples

### Features
- **Instance Discovery**: Find all EC2 instances tagged with specific `crdb_cluster_name`
- **ASG Integration**: Correlate instances with their Auto Scaling Groups
- **Multi-Region Support**: Query instances across different AWS regions
- **Profile Support**: Use different AWS profiles for access
- **Debug Mode**: Verbose output for troubleshooting
- **Output Options**: Save reports to file or display in terminal
- **Cluster Discovery**: List all available CRDB clusters in a region

### Dependencies
- Python 3.8+
- boto3 >= 1.28.0
- AWS CLI configured with appropriate credentials

### AWS Permissions Required
- `ec2:DescribeInstances`
- `autoscaling:DescribeAutoScalingGroups`
