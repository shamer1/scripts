# NOTES:
# mostly just leave this at 100, but if you insist:
#
# data_volume_size_gb = requested_cluster_capacity_in_GB / (num_subnets * num_instances_per_subnet) / data_volumes_qty / 0.75
#  lite-app-uploader-prod USABLE:  431.6 GiB
#     data_volume_size_gb      = 100
#     data_volumes_qty         = 1
#     num_subnets              = 3
#     num_instances_per_subnet = 2
#     requested size           = ??

TARGET_PERCENTAGE = 0.75

def reszie_for_x_percent(percent, current_capacity, instance_count, data_vols):
    """Function resize_for_x_percent"""
    # take a percentage from cli
    # take current size from cli
    # display final size

    y = percent / 100
    z = y * current_capacity
    print(f'{y}% of {current_capacity} is {z}')

def resize_for_x_size():
    """Function resize_for_x_size"""
    # take an input size
    # take current size
    # display new size, and new percentage
    pass

def base(requested_cluster_capacity_in_gb, num_subnets, num_instances_per, data_volumes_qty, data_volumes_size):
    """Function base"""
    data_volumes_size = requested_cluster_capacity_in_gb / (num_subnets * num_instances_per) / data_volumes_qty / TARGET_PERCENTAGE
    crdb_total = num_subnets * num_instances_per * (data_volumes_size * data_volumes_qty) * TARGET_PERCENTAGE
    raw_total = num_subnets * num_instances_per * (data_volumes_size * data_volumes_qty)

    print("\n")
    print(f"Data Volumes:           {int(data_volumes_qty)}")
    print(f"Data Volume Size GB:    {int(data_volumes_size)} GB     {int(data_volumes_size) / 1000} TB")
    print(f"CRDB Total:             {int(crdb_total)} GB  {int(crdb_total) / 1000 } TB"  )
    print(f"RAW total               {int(raw_total)} GB    {int(raw_total) / 1000 } TB"  )


def menu():
    """Function Menu"""
    # Will house the menu.
    while True:
        print("\nChoose from the following:")
        print("===========================")
        print("\n1. Compute the default storage config")
        print("2. Compute to percentage (eg currently at 34% what is needed to get to (n)%)")
        print("3. Compute to size (eg Current size it 9TB, what is needed to go to  (n)TB  )")
        print("4. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            # Calculate cluster volumes size on new creation 
            while True:
                requested_cluster_capacity_in_gb    = int(input("\nEnter the requested cluster capacity in GB: "))            
 
                num_subnets                         = int(input("Enter the number of subnets [3]: ").strip() or "3")
                num_instances_per                   = int(input("Enter the number of instance per subnet [1]: ").strip() or "1")
                data_volumes_qty                    = int(input("Enter the data volumes per instance [1]: ").strip() or "1")
                data_volumes_size                   = int(input("Enter the data volume size [100]: ").strip() or "100")   

                base(requested_cluster_capacity_in_gb, num_subnets, num_instances_per, data_volumes_qty, data_volumes_size )
                break
        elif choice == '2':
            # Resize to a specific percentage 
            while True:
                percent          = int(input("Enter target percent: "))
                current_capacity = int(input("Enter current capacity: "))
                instance_count   = int(input("Enter the instance count: "))
                data_vols        = int(input("Enter the number of data volumes per instance: "))
                reszie_for_x_percent(percent, current_capacity, instance_count, data_vols )
                break
        elif choice == '3':
            # Resize based on size
            print("3")
        elif choice == '4':
            print("Goodbye!")
            break
        else:
            print("Invalid choice")

def main():
    """Function main"""
    # call cli argument parser.
    # parser()
    # call menu driven parser.
    menu()

if __name__ == "__main__":
    main()
