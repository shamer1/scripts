import boto3

def get_health_events(session):
    health = session.client("health", region_name="us-east-1")
    response = health.describe_events()
    events = []
    for event in response.get("events", []):
        if event.get("statusCode") == "upcoming":
            # Get affected entities for this event
            entities_resp = health.describe_affected_entities(
                filter={"eventArns": [event["arn"]]}
            )
            instance_ids = []
            for entity in entities_resp.get("entities", []):
                if entity.get("entityValue", "").startswith("i-"):
                    instance_ids.append(entity["entityValue"])
            events.append({
                #"Arn": event.get("arn"),
                #"Service": event.get("service"),
                "EventTypeCode": event.get("eventTypeCode"),
                #"EventTypeCategory": event.get("eventTypeCategory"),
                #"StartTime": event.get("startTime"),
                #"EndTime": event.get("endTime"),
                #"StatusCode": event.get("statusCode"),
                #"Region": event.get("region"),
                "InstanceIds": instance_ids,
            })
    return events

def main():
    # Initialize the boto3 session (uses default credentials)
    session = boto3.Session()

    # Import the utility functions
    from utils.aws_events import get_ec2_events, get_ebs_events

    # Retrieve scheduled EC2 and EBS events
    ec2_events = get_ec2_events(session)
    ebs_events = get_ebs_events(session)

    # Retrieve AWS Health events (filtered for 'upcoming' status)
    health_events = get_health_events(session)

    # Print the events
    print("Scheduled EC2 Events (Status: upcoming):")
    for event in ec2_events:
        # Only print EC2 events with StatusCode 'upcoming'
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
        print(event)

if __name__ == "__main__":
    main()