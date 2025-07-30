#!/usr/bin/env python3
"""
Script to lookup AWS instances by crdb_cluster_name tag.
Provides detailed instance information including launch template versions, AMI IDs, private IP addresses, and availability zones.

Usage examples:
  # List all available CRDB clusters
  python3 asg_report.py --list-clusters

  # Generate report for a specific CRDB cluster
  python3 asg_report.py --crdb-cluster-name my-cluster

  # Generate report with debug output
  python3 asg_report.py --crdb-cluster-name my-cluster --debug

  # Generate report with specific AWS profile and region
  python3 asg_report.py --profile prod --region us-west-2 --crdb-cluster-name my-cluster

  # Save report to file
  python3 asg_report.py --crdb-cluster-name my-cluster --output cluster_instances.txt
"""

import boto3
import json
import sys
from collections import defaultdict, Counter
from datetime import datetime
import argparse


def get_session(profile=None, region=None):
    """Create boto3 session with optional profile and region.
    
    Args:
        profile (str, optional): AWS profile name to use for authentication.
            If None, uses default credentials chain. Defaults to None.
        region (str, optional): AWS region to connect to. If None, uses
            session's default region or falls back to us-east-1. Defaults to None.
    
    Returns:
        tuple: A tuple containing:
            - boto3.Session: Configured boto3 session object
            - str: The region name that will be used for API calls
    
    Example:
        >>> session, region = get_session('production', 'us-west-2')
        >>> session, region = get_session()  # Use default profile and region
    """
    if profile:
        session = boto3.Session(profile_name=profile)
    else:
        session = boto3.Session()
    
    if region:
        return session, region
    else:
        # Use session's region or default to us-east-1
        return session, session.region_name or 'us-east-1'


def list_crdb_clusters(ec2_client, debug=False):
    """List all unique crdb_cluster_name values from instance tags.
    
    Scans all EC2 instances across the region to find unique values of the
    'crdb_cluster_name' tag. This is useful for discovering available clusters
    before running detailed reports.
    
    Args:
        ec2_client (boto3.client): Configured EC2 client for API calls
        debug (bool, optional): Enable verbose debug output showing discovery
            progress and found clusters. Defaults to False.
    
    Returns:
        list: Sorted list of unique CRDB cluster names found in instance tags.
            Returns empty list if no clusters found or on error.
    
    Example:
        >>> ec2 = session.client('ec2', region_name='us-west-2')
        >>> clusters = list_crdb_clusters(ec2, debug=True)
        >>> print(clusters)
        ['cluster-prod', 'cluster-staging', 'cluster-test']
    """
    try:
        crdb_clusters = set()
        paginator = ec2_client.get_paginator('describe_instances')
        
        if debug:
            print("Scanning all instances for crdb_cluster_name tags...")
        
        instance_count = 0
        for page in paginator.paginate():
            for reservation in page['Reservations']:
                for instance in reservation['Instances']:
                    instance_count += 1
                    for tag in instance.get('Tags', []):
                        if tag['Key'] == 'crdb_cluster_name':
                            crdb_clusters.add(tag['Value'])
                            if debug:
                                print(f"  Found cluster: {tag['Value']} on instance {instance['InstanceId']}")
        
        if debug:
            print(f"Scanned {instance_count} instances total")
        
        return sorted(list(crdb_clusters))
    except Exception as e:
        print(f"Error retrieving CRDB clusters: {e}")
        return []


def get_instances_by_crdb_cluster(ec2_client, crdb_cluster_name, debug=False):
    """Get all instances with a specific crdb_cluster_name tag.
    
    Efficiently retrieves EC2 instances that have a specific value for the
    'crdb_cluster_name' tag using API filters. Only includes instances in
    active states (pending, running, shutting-down, stopping, stopped).
    
    Args:
        ec2_client (boto3.client): Configured EC2 client for API calls
        crdb_cluster_name (str): The cluster name to filter instances by
        debug (bool, optional): Enable verbose debug output showing search
            progress and found instances. Defaults to False.
    
    Returns:
        list: List of EC2 instance dictionaries matching the cluster name.
            Each dictionary contains full instance details from the EC2 API.
            Returns empty list if no instances found or on error.
    
    Example:
        >>> ec2 = session.client('ec2', region_name='us-west-2')
        >>> instances = get_instances_by_crdb_cluster(ec2, 'prod-cluster')
        >>> print(f"Found {len(instances)} instances")
    """
    try:
        instances = []
        
        if debug:
            print(f"Searching for instances with crdb_cluster_name tag: {crdb_cluster_name}")
        
        # Use filters to efficiently find instances with the specific tag
        paginator = ec2_client.get_paginator('describe_instances')
        page_filters = [
            {
                'Name': 'tag:crdb_cluster_name',
                'Values': [crdb_cluster_name]
            },
            {
                'Name': 'instance-state-name',
                'Values': ['pending', 'running', 'shutting-down', 'stopping', 'stopped']
            }
        ]
        
        instance_count = 0
        for page in paginator.paginate(Filters=page_filters):
            for reservation in page['Reservations']:
                for instance in reservation['Instances']:
                    instance_count += 1
                    instances.append(instance)
                    if debug:
                        print(f"  Found instance: {instance['InstanceId']} in AZ: {instance.get('Placement', {}).get('AvailabilityZone', 'Unknown')}")
        
        if debug:
            print(f"Total instances found: {instance_count}")
        
        return instances
    except Exception as e:
        print(f"Error retrieving instances: {e}")
        return []


def get_asgs_by_crdb_cluster(autoscaling_client, crdb_cluster_name, debug=False):
    """Get all Auto Scaling Groups with a specific crdb_cluster_name tag.
    
    Searches through all Auto Scaling Groups in the region to find those
    tagged with the specified crdb_cluster_name. This enables correlation
    between instances and their managing ASGs.
    
    Args:
        autoscaling_client (boto3.client): Configured Auto Scaling client for API calls
        crdb_cluster_name (str): The cluster name to filter ASGs by
        debug (bool, optional): Enable verbose debug output showing search
            progress and found ASGs. Defaults to False.
    
    Returns:
        list: List of Auto Scaling Group dictionaries matching the cluster name.
            Each dictionary contains full ASG details from the Auto Scaling API.
            Returns empty list if no ASGs found or on error.
    
    Example:
        >>> asg_client = session.client('autoscaling', region_name='us-west-2')
        >>> asgs = get_asgs_by_crdb_cluster(asg_client, 'prod-cluster')
        >>> print(f"Found {len(asgs)} ASGs")
    """
    try:
        asgs = []
        
        if debug:
            print(f"Searching for ASGs with crdb_cluster_name tag: {crdb_cluster_name}")
        
        paginator = autoscaling_client.get_paginator('describe_auto_scaling_groups')
        
        asg_count = 0
        for page in paginator.paginate():
            for asg in page['AutoScalingGroups']:
                # Check if ASG has the crdb_cluster_name tag
                for tag in asg.get('Tags', []):
                    if tag['Key'] == 'crdb_cluster_name' and tag['Value'] == crdb_cluster_name:
                        asg_count += 1
                        asgs.append(asg)
                        if debug:
                            print(f"  Found ASG: {asg['AutoScalingGroupName']}")
                        break
        
        if debug:
            print(f"Total ASGs found: {asg_count}")
        
        return asgs
    except Exception as e:
        print(f"Error retrieving ASGs: {e}")
        return []


def extract_instance_info(instance, asg_instance_map, debug=False):
    """Extract relevant information from an EC2 instance.
    
    Processes an EC2 instance dictionary from the AWS API and extracts key
    information needed for reporting. Correlates instance data with ASG
    information when available.
    
    Args:
        instance (dict): EC2 instance dictionary from describe_instances API
        asg_instance_map (dict): Mapping of instance IDs to ASG information.
            Expected format: {instance_id: {'asg_name': str, 'lifecycle_state': str}}
        debug (bool, optional): Enable verbose debug output showing extraction
            progress and found details. Defaults to False.
    
    Returns:
        dict: Dictionary containing extracted instance information with keys:
            - instance_id (str): EC2 instance ID
            - launch_template_version (str): Launch template version or 'N/A'
            - launch_template_id (str): Launch template ID or 'N/A'
            - launch_template_name (str): Launch template name or 'N/A'
            - ami_id (str): AMI ID used by the instance
            - instance_type (str): EC2 instance type
            - state (str): Current instance state
            - availability_zone (str): AZ where instance is running
            - private_ip (str): Private IPv4 address
            - launch_time (str): ISO formatted launch time
            - crdb_cluster_name (str): Cluster name from tags
            - asg_name (str): Auto Scaling Group name or 'N/A'
            - asg_lifecycle_state (str): ASG lifecycle state or 'N/A'
    
    Example:
        >>> info = extract_instance_info(instance_data, asg_map)
        >>> print(f"Instance {info['instance_id']} in {info['availability_zone']}")
    """
    instance_id = instance['InstanceId']
    
    # Get launch template version from tag
    launch_template_version = 'N/A'
    crdb_cluster_name = 'N/A'
    
    for tag in instance.get('Tags', []):
        if tag['Key'] == 'aws:ec2launchtemplate:version':
            launch_template_version = tag['Value']
        elif tag['Key'] == 'crdb_cluster_name':
            crdb_cluster_name = tag['Value']
    
    # Extract basic instance information
    ami_id = instance.get('ImageId', 'N/A')
    instance_type = instance.get('InstanceType', 'N/A')
    state = instance.get('State', {}).get('Name', 'N/A')
    availability_zone = instance.get('Placement', {}).get('AvailabilityZone', 'N/A')
    private_ip = instance.get('PrivateIpAddress', 'N/A')
    launch_time = instance.get('LaunchTime')
    launch_time_str = launch_time.isoformat() if launch_time else 'N/A'
    
    # Get launch template information if available
    launch_template_id = 'N/A'
    launch_template_name = 'N/A'
    
    if 'LaunchTemplate' in instance:
        lt_info = instance['LaunchTemplate']
        launch_template_id = lt_info.get('LaunchTemplateId', 'N/A')
        launch_template_name = lt_info.get('LaunchTemplateName', 'N/A')
        if debug:
            print(f"  Instance {instance_id} launch template: {launch_template_name} ({launch_template_id})")
    
    # Get ASG information for this instance
    asg_name = 'N/A'
    asg_lifecycle_state = 'N/A'
    
    if instance_id in asg_instance_map:
        asg_info = asg_instance_map[instance_id]
        asg_name = asg_info['asg_name']
        asg_lifecycle_state = asg_info['lifecycle_state']
        if debug:
            print(f"  Instance {instance_id} is in ASG: {asg_name} with lifecycle state: {asg_lifecycle_state}")
    
    return {
        'instance_id': instance_id,
        'launch_template_version': launch_template_version,
        'launch_template_id': launch_template_id,
        'launch_template_name': launch_template_name,
        'ami_id': ami_id,
        'instance_type': instance_type,
        'state': state,
        'availability_zone': availability_zone,
        'private_ip': private_ip,
        'launch_time': launch_time_str,
        'crdb_cluster_name': crdb_cluster_name,
        'asg_name': asg_name,
        'asg_lifecycle_state': asg_lifecycle_state
    }


def analyze_instances(session, region, crdb_cluster_name, debug=False):
    """Main function to analyze instances by crdb_cluster_name tag.
    
    Orchestrates the complete analysis workflow:
    1. Discovers EC2 instances with the specified cluster tag
    2. Finds related Auto Scaling Groups
    3. Correlates instances with their ASGs
    4. Generates comprehensive report with multiple summary sections
    
    The report includes detailed instance tables and statistical summaries
    organized by ASG, availability zone, launch template version, instance
    state, and ASG lifecycle state.
    
    Args:
        session (boto3.Session): Configured boto3 session for AWS API access
        region (str): AWS region to query for instances and ASGs
        crdb_cluster_name (str): The cluster name to filter instances by
        debug (bool, optional): Enable verbose debug output throughout the
            analysis process. Defaults to False.
    
    Returns:
        None: Prints formatted report to stdout. Returns early if no instances found.
    
    Example:
        >>> session, region = get_session('prod', 'us-west-2')
        >>> analyze_instances(session, region, 'merchant-svc-prod', debug=True)
    
    Note:
        Requires appropriate AWS permissions:
        - ec2:DescribeInstances
        - autoscaling:DescribeAutoScalingGroups
    """
    ec2_client = session.client('ec2', region_name=region)
    autoscaling_client = session.client('autoscaling', region_name=region)
    
    # Get instances
    instances = get_instances_by_crdb_cluster(ec2_client, crdb_cluster_name, debug)
    
    if not instances:
        print(f"No instances found with crdb_cluster_name tag: {crdb_cluster_name}")
        return
    
    # Get ASGs for the same cluster
    asgs = get_asgs_by_crdb_cluster(autoscaling_client, crdb_cluster_name, debug)
    
    # Create a mapping of instance ID to ASG information
    asg_instance_map = {}
    for asg in asgs:
        asg_name = asg['AutoScalingGroupName']
        for asg_instance in asg.get('Instances', []):
            instance_id = asg_instance['InstanceId']
            lifecycle_state = asg_instance.get('LifecycleState', 'Unknown')
            asg_instance_map[instance_id] = {
                'asg_name': asg_name,
                'lifecycle_state': lifecycle_state
            }
            if debug:
                print(f"  Mapped instance {instance_id} to ASG {asg_name} with state {lifecycle_state}")
    
    # Process instance information
    instance_info_list = []
    for instance in instances:
        info = extract_instance_info(instance, asg_instance_map, debug)
        instance_info_list.append(info)
    
    # Sort by ASG name, then availability zone, then instance ID
    instance_info_list.sort(key=lambda x: (x['asg_name'], x['availability_zone'], x['instance_id']))
    
    # Generate report
    print("=" * 200)
    print(f"INSTANCE REPORT FOR CRDB CLUSTER: {crdb_cluster_name}")
    print(f"Region: {region}")
    print(f"Total Instances Found: {len(instance_info_list)}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 200)
    
    # Instance details table
    print(f"\nINSTANCE DETAILS:")
    print(f"{'Instance ID':<20} {'ASG Name':<55} {'ASG State':<15} {'LT Ver':<8} {'AMI ID':<21} {'Type':<15} {'State':<12} {'Private IP':<15} {'AZ':<15}")
    print("-" * 200)
    
    az_counts = Counter()
    lt_version_counts = Counter()
    state_counts = Counter()
    asg_counts = Counter()
    asg_lifecycle_counts = Counter()
    
    for info in instance_info_list:
        print(f"{info['instance_id']:<20} "
              f"{info['asg_name']:<55} "
              f"{info['asg_lifecycle_state']:<15} "
              f"{info['launch_template_version']:<8} "
              f"{info['ami_id']:<21} "
              f"{info['instance_type']:<15} "
              f"{info['state']:<12} "
              f"{info['private_ip']:<15} "
              f"{info['availability_zone']:<15}")
        
        # Count statistics
        az_counts[info['availability_zone']] += 1
        lt_version_counts[info['launch_template_version']] += 1
        state_counts[info['state']] += 1
        asg_counts[info['asg_name']] += 1
        asg_lifecycle_counts[info['asg_lifecycle_state']] += 1
    
    # ASG Summary
    print(f"\n{'='*40} AUTO SCALING GROUP SUMMARY {'='*40}")
    print(f"{'ASG Name':<60} {'Instance Count':<15}")
    print("-" * 75)
    for asg, count in sorted(asg_counts.items()):
        print(f"{asg:<60} {count:<15}")
    
    # Availability Zone Summary
    print(f"\n{'='*40} AVAILABILITY ZONE SUMMARY {'='*40}")
    print(f"{'Availability Zone':<20} {'Instance Count':<15}")
    print("-" * 35)
    for az, count in sorted(az_counts.items()):
        print(f"{az:<20} {count:<15}")
    
    # Launch Template Version Summary
    print(f"\n{'='*40} LAUNCH TEMPLATE VERSION SUMMARY {'='*35}")
    print(f"{'Template Version':<20} {'Instance Count':<15}")
    print("-" * 35)
    for version, count in sorted(lt_version_counts.items()):
        print(f"{version:<20} {count:<15}")
    
    # Instance State Summary
    print(f"\n{'='*40} INSTANCE STATE SUMMARY {'='*40}")
    print(f"{'State':<20} {'Instance Count':<15}")
    print("-" * 35)
    for state, count in sorted(state_counts.items()):
        print(f"{state:<20} {count:<15}")
    
    # ASG Lifecycle State Summary
    print(f"\n{'='*40} ASG LIFECYCLE STATE SUMMARY {'='*35}")
    print(f"{'Lifecycle State':<20} {'Instance Count':<15}")
    print("-" * 35)
    for lifecycle_state, count in sorted(asg_lifecycle_counts.items()):
        print(f"{lifecycle_state:<20} {count:<15}")
    
    # Additional details if debug is enabled
    if debug:
        print(f"\n{'='*40} DEBUG: LAUNCH TEMPLATE DETAILS {'='*30}")
        template_details = defaultdict(list)
        for info in instance_info_list:
            if info['launch_template_name'] != 'N/A':
                key = f"{info['launch_template_name']} (v{info['launch_template_version']})"
                template_details[key].append(info['instance_id'])
        
        for template, instance_ids in sorted(template_details.items()):
            print(f"\n{template}:")
            for instance_id in instance_ids:
                print(f"  - {instance_id}")


def main():
    """Main entry point for the ASG report tool.
    
    Handles command-line argument parsing, AWS session setup, and coordinates
    the execution of different reporting modes (list clusters vs analyze cluster).
    Provides error handling and debug output management.
    
    Command-line Arguments:
        --profile: AWS profile to use for authentication
        --region: AWS region to query (defaults to session default)
        --crdb-cluster-name: Target cluster name for analysis
        --list-clusters: List available clusters and exit
        --debug: Enable verbose debug output
        --output: File path to save report (defaults to stdout)
    
    Exit Codes:
        0: Success
        1: Error occurred (missing arguments, AWS errors, etc.)
    
    Example:
        Command line usage:
        $ python asg_report.py --crdb-cluster-name prod-cluster --debug
        $ python asg_report.py --list-clusters --region us-west-2
        $ python asg_report.py --crdb-cluster-name test --output report.txt
    
    Note:
        Either --list-clusters or --crdb-cluster-name must be provided.
        AWS credentials must be configured via CLI, environment variables,
        or IAM roles.
    """
    parser = argparse.ArgumentParser(description='Lookup AWS instances by crdb_cluster_name tag')
    parser.add_argument('--profile', help='AWS profile to use')
    parser.add_argument('--region', help='AWS region to query (default: session default)')
    parser.add_argument('--crdb-cluster-name', help='Filter instances by crdb_cluster_name tag')
    parser.add_argument('--list-clusters', action='store_true', help='List available CRDB cluster names and exit')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--output', help='Output file path (default: stdout)')
    
    args = parser.parse_args()
    
    try:
        session, region = get_session(args.profile, args.region)
        if args.debug:
            print(f"Using region: {region}")
            if args.profile:
                print(f"Using profile: {args.profile}")
        
        # Handle list clusters option
        if args.list_clusters:
            ec2_client = session.client('ec2', region_name=region)
            clusters = list_crdb_clusters(ec2_client, args.debug)
            if clusters:
                print(f"\nAvailable CRDB clusters in {region}:")
                for cluster in clusters:
                    print(f"  - {cluster}")
            else:
                print(f"No CRDB clusters found in {region}")
            return
        
        # Require crdb-cluster-name if not listing clusters
        if not args.crdb_cluster_name:
            print("Error: --crdb-cluster-name is required unless using --list-clusters")
            parser.print_help()
            sys.exit(1)
        
        if args.output:
            # Redirect stdout to file
            import contextlib
            with open(args.output, 'w') as f:
                with contextlib.redirect_stdout(f):
                    analyze_instances(session, region, args.crdb_cluster_name, args.debug)
            print(f"Report saved to: {args.output}")
        else:
            analyze_instances(session, region, args.crdb_cluster_name, args.debug)
            
    except Exception as e:
        print(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
