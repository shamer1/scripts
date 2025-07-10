def get_ec2_events(session):
    ec2_client = session.client('ec2')
    response = ec2_client.describe_instance_status(
        IncludeAllInstances=True,
        Filters=[
            {
                'Name': 'event.code',
                'Values': ['instance-reboot', 'instance-retirement', 'instance-stop']
            }
        ]
    )
    return response['InstanceStatuses']


def get_ebs_events(session):
    ec2_client = session.client('ec2')
    response = ec2_client.describe_volumes_modifications()
    return response['VolumesModifications']