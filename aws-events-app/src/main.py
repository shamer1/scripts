import boto3

def main():
    # Initialize the boto3 session (uses default credentials)
    session = boto3.Session()

    # Import the utility functions
    from utils.aws_events import get_ec2_events, get_ebs_events

    # Retrieve scheduled EC2 and EBS events
    ec2_events = get_ec2_events(session)
    ebs_events = get_ebs_events(session)

    # Print the events
    print("Scheduled EC2 Events:")
    for event in ec2_events:
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




if __name__ == "__main__":
    main()