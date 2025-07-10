def get_ec2_events(session):
    ec2 = session.client("ec2")
    response = ec2.describe_instance_status(
        IncludeAllInstances=True
    )
    print(response)
    events = []
    for status in response.get("InstanceStatuses", []):
        instance_id = status["InstanceId"]
        for event in status.get("Events", []):
            events.append({
                "InstanceId": instance_id,
                "EventId": event.get("InstanceEventId"),
                "EventType": event.get("Code"),
                "Description": event.get("Description"),
                "NotBefore": event.get("NotBefore"),
                "NotAfter": event.get("NotAfter"),
                "State": event.get("NotBefore"),
            })
    return events


def get_ebs_events(session):
    ec2_client = session.client('ec2')
    response = ec2_client.describe_volumes_modifications()
    return response['VolumesModifications']