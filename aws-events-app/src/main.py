import boto3

def get_instance_details(session, instance_ids):
    """Fetch tag values and private IP for a list of instance IDs."""
    ec2 = session.client("ec2")
    details = {}
    if not instance_ids:
        return details
    response = ec2.describe_instances(InstanceIds=instance_ids)
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
            details[instance["InstanceId"]] = {
                "crdb_cluster_name": tags.get("crdb_cluster_name"),
                "tier": tags.get("tier"),
                "node_id": tags.get("node_id"),
                "private_ip": instance.get("PrivateIpAddress"),
            }
    return details

def get_health_events(session):
    health = session.client("health", region_name="us-east-1")
    response = health.describe_events()
    events = []
    for event in response.get("events", []):
        if event.get("statusCode") == "upcoming":
            entities_resp = health.describe_affected_entities(
                filter={"eventArns": [event["arn"]]}
            )
            instance_ids = [
                entity["entityValue"]
                for entity in entities_resp.get("entities", [])
                if entity.get("entityValue", "").startswith("i-")
            ]
            # Lookup instance details for these IDs
            instance_details = get_instance_details(session, instance_ids)
            events.append({
                "EventTypeCode": event.get("eventTypeCode"),
                "InstanceIds": instance_ids,
                "InstanceDetails": instance_details,
            })
    return events

def main():
    session = boto3.Session()
    from utils.aws_events import get_ec2_events, get_ebs_events

    ec2_events = get_ec2_events(session)
    ebs_events = get_ebs_events(session)
    health_events = get_health_events(session)

    print("Scheduled EC2 Events (Status: upcoming):")
    for event in ec2_events:
        if event.get("StatusCode") == "upcoming":
            print(event)

    print("\nScheduled EBS Events:")
    for event in ebs_events:
        mod_state = event.get("ModificationState")
        if mod_state != "completed":
            volume_id = event.get("VolumeId")
            start_time = event.get("StartTime")
            if mod_state == "failed":
                target_size = event.get("TargetSize")
                target_iops = event.get("TargetIops")
                target_throughput = event.get("TargetThroughput")
                original_size = event.get("OriginalSize")
                original_iops = event.get("OriginalIops")
                original_throughput = event.get("OriginalThroughput")
                print(
                    f"FAILED: VolumeId: {volume_id}, StartTime: {start_time}, "
                    f"TargetSize: {target_size}, TargetIops: {target_iops}, TargetThroughput: {target_throughput}, "
                    f"OriginalSize: {original_size}, OriginalIops: {original_iops}, OriginalThroughput: {original_throughput}"
                )
            else:
                print(f"VolumeId: {volume_id}, StartTime: {start_time}")

    print("\nAWS Health Events (Status: upcoming):")
    for event in health_events:
        print(f"EventTypeCode: {event['EventTypeCode']}")
        for instance_id in event["InstanceIds"]:
            details = event["InstanceDetails"].get(instance_id, {})
            print(
                f"  InstanceId: {instance_id}, "
                f"crdb_cluster_name: {details.get('crdb_cluster_name')}, "
                f"tier: {details.get('tier')}, "
                f"node_id: {details.get('node_id')}, "
                f"private_ip: {details.get('private_ip')}"
            )

if __name__ == "__main__":
    main()