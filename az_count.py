import boto3
import argparse
from collections import Counter

def count_instances_by_az(cluster_name):
    ec2 = boto3.client('ec2')

    filters = [
        {'Name': 'tag:crdb_cluster_name', 'Values': [cluster_name]},
        {'Name': 'instance-state-name', 'Values': ['running']}
    ]
    
    paginator = ec2.get_paginator('describe_instances')
    response_iterator = paginator.paginate(Filters=filters)

    az_counter = Counter()

    for page in response_iterator:
        for reservation in page['Reservations']:
            for instance in reservation['Instances']:
                az = instance.get('Placement', {}).get('AvailabilityZone', 'unknown')
                az_counter[az] += 1

    return az_counter

def main():
    parser = argparse.ArgumentParser(description='Count AWS EC2 instances by AZ for a given crdb_cluster_name tag')
    parser.add_argument('cluster_name', help='Value of the crdb_cluster_name tag to filter instances')
    args = parser.parse_args()

    cluster_name = args.cluster_name.replace("-", "_")
    az_counts = count_instances_by_az(cluster_name)

    print(f"Instances in cluster '{args.cluster_name}' by Availability Zone:")
    for az, count in sorted(az_counts.items()):
        print(f"{az}: {count}")

if __name__ == '__main__':
    main()
