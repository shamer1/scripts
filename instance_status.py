import boto3
import argparse

EXCLUDED_STATES = {"running", "shutting-down", "terminated"}  # states to ignore
MISSING_NAME_PLACEHOLDER = "<no-name>"

def extract_name(tags):
    if not tags:
        return MISSING_NAME_PLACEHOLDER
    for t in tags:
        if t.get("Key") == "Name":
            return t.get("Value") or MISSING_NAME_PLACEHOLDER
    return MISSING_NAME_PLACEHOLDER

def find_instances(profile=None, regions=None):
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    if not regions:
        # discover all regions
        ec2 = session.client("ec2")
        regions = [r["RegionName"] for r in ec2.describe_regions()["Regions"]]

    results = []
    for region in regions:
        ec2 = session.client("ec2", region_name=region)
        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    state = inst["State"]["Name"]
                    if state not in EXCLUDED_STATES:
                        name = extract_name(inst.get("Tags"))
                        results.append({
                            "Region": region,
                            "InstanceId": inst["InstanceId"],
                            "State": state,
                            "InstanceType": inst.get("InstanceType"),
                            "Name": name
                        })
    return results

def main():
    parser = argparse.ArgumentParser(description="Find EC2 instances not running or terminating, output Name tag.")
    parser.add_argument("--profile", help="AWS profile name")
    parser.add_argument("--regions", nargs="*", help="Specific region(s) (default: all)")
    parser.add_argument("--csv", action="store_true", help="Output CSV")
    parser.add_argument("--names-only", action="store_true", help="Only print the Name tag values")
    args = parser.parse_args()

    rows = find_instances(profile=args.profile, regions=args.regions)
    if args.names_only:
        # Just the Name tag values (unique, preserve order)
        seen = set()
        for r in rows:
            name = r["Name"]
            if name not in seen:
                print(name)
                seen.add(name)
        return

    if args.csv:
        import csv, sys
        writer = csv.DictWriter(sys.stdout, fieldnames=["Region","InstanceId","State","InstanceType","Name"])
        writer.writeheader()
        writer.writerows(rows)
    else:
        for r in rows:
            print(f"{r['Region']} {r['InstanceId']} {r['State']} {r['InstanceType']} Name='{r['Name']}'")

if __name__ == "__main__":
    main()