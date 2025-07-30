#!/usr/bin/env python3
"""
Script to output Launch Template information for each instance in autoscaling groups.
Provides a detailed report and summary of unique launch templates.
Note: This script only analyzes ASGs using Launch Templates, ignoring Launch Configurations.

Usage examples:
  # List all available CRDB clusters
  python3 asg_launch_config_report.py --list-clusters

  # Generate report for a specific CRDB cluster
  python3 asg_launch_config_report.py --crdb-cluster-name my-cluster

  # Generate report with debug output to troubleshoot missing ASGs
  python3 asg_launch_config_report.py --crdb-cluster-name my-cluster --debug

  # Generate report with specific AWS profile and region
  python3 asg_launch_config_report.py --profile prod --region us-west-2 --crdb-cluster-name my-cluster

  # Save report to file
  python3 asg_launch_config_report.py --crdb-cluster-name my-cluster --output cluster_report.txt

  # Analyze specific ASGs by name
  python3 asg_launch_config_report.py --asg-names asg-1 asg-2 asg-3

  # List all ASGs with Launch Templates (no filtering) with debug info
  python3 asg_launch_config_report.py --debug
"""

import boto3
import json
import sys
from collections import defaultdict, Counter
from datetime import datetime
import argparse


def get_session(profile=None, region=None):
    """Create boto3 session with optional profile and region."""
    if profile:
        session = boto3.Session(profile_name=profile)
    else:
        session = boto3.Session()
    
    if region:
        return session, region
    else:
        # Use session's region or default to us-east-1
        return session, session.region_name or 'us-east-1'


def list_crdb_clusters(autoscaling_client):
    """List all unique crdb_cluster_name values from ASG tags."""
    try:
        crdb_clusters = set()
        paginator = autoscaling_client.get_paginator('describe_auto_scaling_groups')
        
        for page in paginator.paginate():
            asgs = page['AutoScalingGroups']
            for asg in asgs:
                for tag in asg.get('Tags', []):
                    if tag['Key'] == 'crdb_cluster_name':
                        crdb_clusters.add(tag['Value'])
        
        return sorted(list(crdb_clusters))
    except Exception as e:
        print(f"Error retrieving CRDB clusters: {e}")
        return []


def get_autoscaling_groups(autoscaling_client, asg_names=None, crdb_cluster_name=None, debug=False):
    """Get autoscaling groups that use launch templates, optionally filtered by crdb_cluster_name tag."""
    try:
        if asg_names:
            # For specific ASG names, we can call directly (no pagination needed for specific names)
            if debug:
                print(f"Fetching specific ASGs: {asg_names}")
            response = autoscaling_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=asg_names
            )
            asgs = response['AutoScalingGroups']
        else:
            # For all ASGs, use pagination to get complete list
            asgs = []
            paginator = autoscaling_client.get_paginator('describe_auto_scaling_groups')
            page_count = 0
            
            if debug:
                print("Fetching all ASGs using pagination...")
            
            for page in paginator.paginate():
                page_count += 1
                page_asgs = page['AutoScalingGroups']
                asgs.extend(page_asgs)
                if debug:
                    print(f"  Page {page_count}: Found {len(page_asgs)} ASGs (total so far: {len(asgs)})")
        
        if debug:
            print(f"Total ASGs retrieved: {len(asgs)}")
        
        # Filter to only ASGs using Launch Templates
        launch_template_asgs = []
        for asg in asgs:
            if 'LaunchTemplate' in asg:
                launch_template_asgs.append(asg)
        
        if debug:
            print(f"ASGs using Launch Templates: {len(launch_template_asgs)} (filtered out {len(asgs) - len(launch_template_asgs)} ASGs using Launch Configurations)")
        
        # Filter by crdb_cluster_name tag if specified
        if crdb_cluster_name:
            filtered_asgs = []
            if debug:
                print(f"Filtering ASGs by crdb_cluster_name tag: {crdb_cluster_name}")
            
            for asg in launch_template_asgs:
                for tag in asg.get('Tags', []):
                    if tag['Key'] == 'crdb_cluster_name' and tag['Value'] == crdb_cluster_name:
                        filtered_asgs.append(asg)
                        if debug:
                            print(f"  Found matching ASG: {asg['AutoScalingGroupName']}")
                        break
            
            if debug:
                print(f"ASGs after filtering: {len(filtered_asgs)}")
            return filtered_asgs
        
        return launch_template_asgs
    except Exception as e:
        print(f"Error retrieving autoscaling groups: {e}")
        return []


def get_launch_template_info(ec2_client, launch_template_id, version):
    """Get launch template details."""
    try:
        # Handle special version specifiers
        if version in ['$Latest', '$Default']:
            # First get the latest version number or default version
            if version == '$Latest':
                # Get the latest version
                response = ec2_client.describe_launch_template_versions(
                    LaunchTemplateId=launch_template_id,
                    Versions=['$Latest']
                )
            else:  # $Default
                response = ec2_client.describe_launch_template_versions(
                    LaunchTemplateId=launch_template_id,
                    Versions=['$Default']
                )
        else:
            # Use the specific version number
            response = ec2_client.describe_launch_template_versions(
                LaunchTemplateId=launch_template_id,
                Versions=[version]
            )
        
        if response['LaunchTemplateVersions']:
            lt_version = response['LaunchTemplateVersions'][0]
            launch_template_data = lt_version['LaunchTemplateData']
            
            # Get the actual version number (not $Latest or $Default)
            actual_version = str(lt_version['VersionNumber'])
            
            return {
                'LaunchTemplateId': launch_template_id,
                'LaunchTemplateName': lt_version['LaunchTemplateName'],
                'Version': actual_version,  # Use actual version number
                'VersionSpecifier': version,  # Keep track of what was requested ($Latest, $Default, or specific number)
                'ImageId': launch_template_data.get('ImageId', 'N/A'),
                'InstanceType': launch_template_data.get('InstanceType', 'N/A'),
                'KeyName': launch_template_data.get('KeyName', 'N/A'),
                'SecurityGroupIds': launch_template_data.get('SecurityGroupIds', []),
                'UserData': 'Present' if launch_template_data.get('UserData') else 'None',
                'IamInstanceProfile': launch_template_data.get('IamInstanceProfile', {}).get('Name', 'N/A'),
                'CreatedBy': lt_version.get('CreatedBy', 'N/A'),
                'CreateTime': lt_version.get('CreateTime').isoformat() if lt_version.get('CreateTime') else 'N/A'
            }
    except Exception as e:
        print(f"Error retrieving launch template {launch_template_id} version {version}: {e}")
        return None


def get_instance_launch_info(ec2_client, instance_id, debug=False):
    """Get launch template information for a specific instance."""
    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        
        if response['Reservations'] and response['Reservations'][0]['Instances']:
            instance = response['Reservations'][0]['Instances'][0]
            
            if debug:
                print(f"  Debug: Instance {instance_id} metadata keys: {list(instance.keys())}")
            
            # Check if instance was launched from a launch template
            if 'LaunchTemplate' in instance:
                lt_info = instance['LaunchTemplate']
                if debug:
                    print(f"  Debug: Instance {instance_id} has LaunchTemplate: {lt_info}")
                
                # Get the actual version from the instance tag (most reliable source)
                actual_version = None
                for tag in instance.get('Tags', []):
                    if tag['Key'] == 'aws:ec2launchtemplate:version':
                        actual_version = str(tag['Value'])
                        break
                
                # Fallback to instance metadata if tag is not found
                if not actual_version:
                    actual_version = str(lt_info['Version'])
                    if debug:
                        print(f"  Debug: aws:ec2launchtemplate:version tag not found, using metadata version: {actual_version}")
                else:
                    if debug:
                        print(f"  Debug: Found launch template version from tag: {actual_version}")
                
                # Get launch template name from template ID (we need this for display)
                template_name = 'Unknown'
                try:
                    template_response = ec2_client.describe_launch_templates(
                        LaunchTemplateIds=[lt_info['LaunchTemplateId']]
                    )
                    if template_response['LaunchTemplates']:
                        template_name = template_response['LaunchTemplates'][0]['LaunchTemplateName']
                        if debug:
                            print(f"  Debug: Retrieved template name: {template_name}")
                except Exception as name_error:
                    if debug:
                        print(f"  Debug: Could not get template name: {name_error}")
                
                # Return instance data with the accurate version from tag
                return {
                    'LaunchTemplateId': lt_info['LaunchTemplateId'],
                    'LaunchTemplateName': template_name,
                    'Version': actual_version,
                    'VersionSpecifier': actual_version,
                    'ImageId': instance.get('ImageId', 'N/A'),
                    'InstanceType': instance.get('InstanceType', 'N/A'),
                    'KeyName': instance.get('KeyName', 'N/A'),
                    'LaunchTime': instance.get('LaunchTime').isoformat() if instance.get('LaunchTime') else 'N/A'
                }
            else:
                if debug:
                    print(f"  Debug: Instance {instance_id} does not have LaunchTemplate field")
                
                # Return basic instance info when launch template isn't available
                return {
                    'LaunchTemplateName': 'N/A',
                    'Version': 'N/A',
                    'VersionSpecifier': 'N/A',
                    'ImageId': instance.get('ImageId', 'N/A'),
                    'InstanceType': instance.get('InstanceType', 'N/A'),
                    'KeyName': instance.get('KeyName', 'N/A'),
                    'LaunchTime': instance.get('LaunchTime').isoformat() if instance.get('LaunchTime') else 'N/A'
                }
    except Exception as e:
        print(f"Error retrieving instance {instance_id}: {e}")
        return None


def analyze_autoscaling_groups(session, region, asg_names=None, crdb_cluster_name=None, debug=False):
    """Main function to analyze autoscaling groups using launch templates."""
    autoscaling_client = session.client('autoscaling', region_name=region)
    ec2_client = session.client('ec2', region_name=region)
    
    asgs = get_autoscaling_groups(autoscaling_client, asg_names, crdb_cluster_name, debug)
    
    if not asgs:
        if crdb_cluster_name:
            print(f"No autoscaling groups with launch templates found with crdb_cluster_name tag: {crdb_cluster_name}")
        else:
            print("No autoscaling groups with launch templates found.")
        return
    
    launch_template_summary = defaultdict(list)
    
    print("=" * 100)
    print(f"AUTOSCALING GROUP LAUNCH TEMPLATE REPORT - {region}")
    if crdb_cluster_name:
        print(f"Filtered by crdb_cluster_name: {crdb_cluster_name}")
    print(f"Total ASGs with Launch Templates found: {len(asgs)}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    
    for asg in asgs:
        asg_name = asg['AutoScalingGroupName']
        print(f"\n{'='*20} {asg_name} {'='*20}")
        
        # Display ASG tags (especially crdb_cluster_name)
        crdb_cluster_tag = None
        for tag in asg.get('Tags', []):
            if tag['Key'] == 'crdb_cluster_name':
                crdb_cluster_tag = tag['Value']
                break
        
        # Get ASG launch template info (we know it has one since we filtered for it)
        lt = asg['LaunchTemplate']
        asg_launch_info = get_launch_template_info(
            ec2_client, 
            lt['LaunchTemplateId'], 
            lt['Version']
        )
        
        if asg_launch_info:
            launch_template_name = asg_launch_info['LaunchTemplateName']
            version = asg_launch_info['Version']  # This is now the actual version number
            version_specifier = asg_launch_info.get('VersionSpecifier', version)
            if version_specifier in ['$Latest', '$Default']:
                template_identifier = f"{launch_template_name}:{version_specifier} (v{version})"
            else:
                template_identifier = f"{launch_template_name}:{version}"
        else:
            template_identifier = 'Unknown'
        
        print(f"Launch Template: {template_identifier}")
        if crdb_cluster_tag:
            print(f"CRDB Cluster Name: {crdb_cluster_tag}")
        if asg_launch_info:
            version_specifier = asg_launch_info.get('VersionSpecifier', asg_launch_info.get('Version', 'N/A'))
            actual_version = asg_launch_info.get('Version', 'N/A')
            print(f"Template Name: {asg_launch_info.get('LaunchTemplateName', 'N/A')}")
            if version_specifier in ['$Latest', '$Default']:
                print(f"Template Version: {version_specifier} (resolves to v{actual_version})")
            else:
                print(f"Template Version: {actual_version}")
            print(f"Template ID: {asg_launch_info.get('LaunchTemplateId', 'N/A')}")
        print(f"Desired Capacity: {asg['DesiredCapacity']}")
        print(f"Current Instances: {len(asg['Instances'])}")
        
        if asg_launch_info:
            print(f"Image ID: {asg_launch_info.get('ImageId', 'N/A')}")
            print(f"Instance Type: {asg_launch_info.get('InstanceType', 'N/A')}")
            print(f"Key Name: {asg_launch_info.get('KeyName', 'N/A')}")
            print(f"Created: {asg_launch_info.get('CreateTime', 'N/A')}")
        
        # Analyze each instance
        print(f"\nInstance Details:")
        print(f"{'Instance ID':<20} {'Template Name':<25} {'Version':<12} {'Image ID':<15} {'Instance Type':<15} {'Status':<15}")
        print("-" * 112)
        
        for instance in asg['Instances']:
            instance_id = instance['InstanceId']
            instance_launch_info = get_instance_launch_info(ec2_client, instance_id, debug)
            
            # Always try to get template info from the ASG as fallback
            if asg_launch_info:
                asg_template_name = asg_launch_info.get('LaunchTemplateName', 'N/A')
                asg_template_version = asg_launch_info.get('Version', 'N/A')
                asg_version_specifier = asg_launch_info.get('VersionSpecifier', asg_template_version)
            else:
                asg_template_name = 'N/A'
                asg_template_version = 'N/A'
                asg_version_specifier = 'N/A'
            
            # Always prioritize actual instance data when available
            if instance_launch_info:
                template_name = instance_launch_info.get('LaunchTemplateName', asg_template_name)
                template_version = instance_launch_info.get('Version', asg_template_version)
                version_specifier = instance_launch_info.get('VersionSpecifier', template_version)
                # Always use the actual AMI and instance type from the running instance
                image_id = instance_launch_info.get('ImageId', 'N/A')
                instance_type = instance_launch_info.get('InstanceType', 'N/A')
                if debug:
                    print(f"  Debug: Using instance data for {instance_id} - Template: {template_name}, Version: {template_version}, AMI: {image_id}, Type: {instance_type}")
            else:
                # Fallback to ASG launch template info only if instance info unavailable
                template_name = asg_template_name
                template_version = asg_template_version
                version_specifier = asg_version_specifier
                if asg_launch_info:
                    image_id = asg_launch_info.get('ImageId', 'N/A')
                    instance_type = asg_launch_info.get('InstanceType', 'N/A')
                    if debug:
                        print(f"  Debug: Instance data unavailable, using ASG template info for {instance_id} - {template_name}:{template_version}")
                else:
                    image_id = 'N/A'
                    instance_type = 'N/A'
                    if debug:
                        print(f"  Debug: No template info available for {instance_id}")
            
            # Format version display - for instances, show the actual version they're using
            version_display = template_version
            
            launch_template = f"{template_name}:{template_version}"
            status = instance['LifecycleState']
            
            print(f"{instance_id:<20} {template_name:<25} {version_display:<12} {image_id:<15} {instance_type:<15} {status:<15}")
            
            # Add to summary
            launch_template_summary[launch_template].append({
                'asg': asg_name,
                'instance': instance_id,
                'image_id': image_id,
                'instance_type': instance_type,
                'template_name': template_name,
                'template_version': template_version
            })
    
    # Print summary
    print(f"\n{'='*20} LAUNCH TEMPLATE SUMMARY {'='*20}")
    print(f"\nUnique Launch Templates Found: {len(launch_template_summary)}")
    print(f"\n{'Template Name':<30} {'Version':<10} {'Count':<8} {'ASGs'}")
    print("-" * 90)
    
    # Sort by count (descending)
    sorted_templates = sorted(launch_template_summary.items(), key=lambda x: len(x[1]), reverse=True)
    
    for template_name, instances in sorted_templates:
        count = len(instances)
        asgs_using = list(set([inst['asg'] for inst in instances]))
        asg_list = ', '.join(asgs_using[:3])  # Show first 3 ASGs
        if len(asgs_using) > 3:
            asg_list += f" (+{len(asgs_using)-3} more)"
        
        # Extract template name and version from the template_name key
        if ':' in template_name:
            name_part, version_part = template_name.split(':', 1)
        else:
            name_part, version_part = template_name, 'N/A'
        
        print(f"{name_part:<30} {version_part:<10} {count:<8} {asg_list}")
    
    # Detailed summary by image ID and instance type
    print(f"\n{'='*20} TEMPLATE DETAILS {'='*20}")
    for template_name, instances in sorted_templates:
        print(f"\nLaunch Template: {template_name}")
        print(f"Total Instances: {len(instances)}")
        
        # Group by image ID and instance type
        template_details = defaultdict(int)
        for inst in instances:
            key = f"{inst['image_id']} ({inst['instance_type']})"
            template_details[key] += 1
        
        for detail, count in sorted(template_details.items()):
            print(f"  {detail}: {count} instances")


def main():
    parser = argparse.ArgumentParser(description='Generate autoscaling group launch template report (Launch Templates only)')
    parser.add_argument('--profile', help='AWS profile to use')
    parser.add_argument('--region', help='AWS region to query (default: session default)')
    parser.add_argument('--asg-names', nargs='+', help='Specific autoscaling group names to analyze')
    parser.add_argument('--crdb-cluster-name', help='Filter ASGs by crdb_cluster_name tag')
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
        else:
            print(f"Using region: {region}")
        
        # Handle list clusters option
        if args.list_clusters:
            autoscaling_client = session.client('autoscaling', region_name=region)
            clusters = list_crdb_clusters(autoscaling_client)
            if clusters:
                print(f"\nAvailable CRDB clusters in {region}:")
                for cluster in clusters:
                    print(f"  - {cluster}")
            else:
                print(f"No CRDB clusters found in {region}")
            return
        
        if args.output:
            # Redirect stdout to file
            import contextlib
            with open(args.output, 'w') as f:
                with contextlib.redirect_stdout(f):
                    analyze_autoscaling_groups(session, region, args.asg_names, args.crdb_cluster_name, args.debug)
            print(f"Report saved to: {args.output}")
        else:
            analyze_autoscaling_groups(session, region, args.asg_names, args.crdb_cluster_name, args.debug)
            
    except Exception as e:
        print(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
