#!/usr/bin/env python3

import json
import subprocess
import os
import glob
import shutil
import argparse
from ddop import DDOP
from colorama import Fore

# Initialize 1Password client
op = DDOP(account="doordash.1password.com")

def get_private_key_file(debug=False):
    """
    Retrieve the private key file from 1Password.
    """
    vault_id = 'lfnuhv7jc72reknrdqlkup2ubm'  # crdb prod vault
    cluster_name = 'nv_serving_inventory-crdb-node-prod-usw2-doordash'

    try:
        # Always show this header
        print(f"{Fore.YELLOW}=== Retrieving 1Password Item Information ==={Fore.RESET}")

        if debug:
            print(f"{Fore.CYAN}Vault ID:{Fore.RESET} {vault_id}")
            print(f"{Fore.CYAN}Cluster Name:{Fore.RESET} {cluster_name}")
            print()

        # Always show this header
        print(f"{Fore.GREEN}=== Getting Item Details ==={Fore.RESET}")

        result = subprocess.run(
            f'op item get "{cluster_name}" --vault {vault_id} --format=json',
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )

        item_json = json.loads(result.stdout)

        if debug:
            # Display basic information
            print(f"{Fore.CYAN}Title:{Fore.RESET} {item_json.get('title', 'N/A')}")
            print(f"{Fore.CYAN}Category:{Fore.RESET} {item_json.get('category', 'N/A')}")
            print(f"{Fore.CYAN}ID:{Fore.RESET} {item_json.get('id', 'N/A')}")
            print()

        # Check for files attached to the item
        if 'files' in item_json and item_json['files']:
            # Always show this header
            print(f"{Fore.YELLOW}=== Attached Files ==={Fore.RESET}")

            for file_info in item_json['files']:
                file_name = file_info.get('name', 'Unknown')
                file_size = file_info.get('size', 'Unknown')
                file_id = file_info.get('id', 'Unknown')

                if debug:
                    print(f"{Fore.CYAN}File Name:{Fore.RESET} {file_name}")
                    print(f"{Fore.CYAN}File Size:{Fore.RESET} {file_size} bytes")
                    print(f"{Fore.CYAN}File ID:{Fore.RESET} {file_id}")
                    print()

                # Use the working alternative method to download the file
                try:
                    # Always show this header
                    print(f"{Fore.GREEN}=== Downloading File: {file_name} ==={Fore.RESET}")

                    output_filename = f"/tmp/{file_name}"

                    # Use op read command which works
                    read_result = subprocess.run(
                        f'op read "op://{vault_id}/{cluster_name}/{file_name}" --out-file "{output_filename}"',
                        shell=True,
                        capture_output=True,
                        text=True,
                        check=True
                    )

                    if os.path.exists(output_filename):
                        if debug:
                            print(f"{Fore.GREEN}File downloaded successfully to: {output_filename}{Fore.RESET}")

                            # Show file info
                            file_stat = os.stat(output_filename)
                            print(f"{Fore.CYAN}Downloaded file size:{Fore.RESET} {file_stat.st_size} bytes")

                            # If it looks like a private key, show some info about it
                            with open(output_filename, 'r') as f:
                                content = f.read()

                            if 'BEGIN' in content and 'PRIVATE KEY' in content:
                                print(f"{Fore.GREEN}✓ Appears to be a private key file{Fore.RESET}")
                                lines = content.split('\n')
                                print(f"{Fore.CYAN}First line:{Fore.RESET} {lines[0] if lines else 'Empty'}")
                                print(f"{Fore.CYAN}Last line:{Fore.RESET} {lines[-2] if len(lines) > 1 else 'Single line'}")
                                print(f"{Fore.CYAN}Total lines:{Fore.RESET} {len(lines)}")
                            else:
                                print(f"{Fore.YELLOW}File content preview (first 200 chars):{Fore.RESET}")
                                print(content[:200] + "..." if len(content) > 200 else content)

                    else:
                        if debug:
                            print(f"{Fore.RED}File not found at expected location: {output_filename}{Fore.RESET}")

                except subprocess.CalledProcessError as e:
                    if debug:
                        print(f"{Fore.RED}Failed to download file {file_name}: {e}{Fore.RESET}")
                        print(f"{Fore.RED}Error: {e.stderr}{Fore.RESET}")

        else:
            if debug:
                print(f"{Fore.YELLOW}No files attached to this item{Fore.RESET}")

                # Try alternative method - maybe it's stored as a document directly
                print(f"\n{Fore.YELLOW}=== Trying document download method ==={Fore.RESET}")

            try:
                output_filename = f"/tmp/{cluster_name}_private_key"
                doc_result = subprocess.run(
                    f'op document get "{cluster_name}" --vault {vault_id} --output "{output_filename}"',
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=True
                )

                if os.path.exists(output_filename):
                    if debug:
                        print(f"{Fore.GREEN}Document downloaded successfully to: {output_filename}{Fore.RESET}")
                else:
                    if debug:
                        print(f"{Fore.RED}Document download failed{Fore.RESET}")

            except subprocess.CalledProcessError as e:
                if debug:
                    print(f"{Fore.RED}Document download failed: {e}{Fore.RESET}")

    except subprocess.CalledProcessError as e:
        if debug:
            print(f"{Fore.RED}Failed to get item details: {e}{Fore.RESET}")
            print(f"{Fore.RED}Error: {e.stderr}{Fore.RESET}")
    except Exception as e:
        if debug:
            print(f"{Fore.RED}Error retrieving private key file: {e}{Fore.RESET}")

def copy_key_to_ssh(debug=False):
    """
    Copy the downloaded private key to SSH directory with proper permissions.
    """
    cluster_name = 'nv_serving_inventory-crdb-node-prod-usw2-doordash'
    temp_files = [
        f"/tmp/{cluster_name}",
        f"/tmp/{cluster_name}_private_key"
    ]

    # Find the downloaded file
    key_file = None
    for temp_file in temp_files:
        if os.path.exists(temp_file):
            key_file = temp_file
            break

    # Also check for any files that might have been downloaded with different names
    temp_pattern_files = glob.glob(f"/tmp/*{cluster_name.split('-')[0]}*") + glob.glob(f"/tmp/*inventory*")
    for temp_file in temp_pattern_files:
        if os.path.exists(temp_file):
            key_file = temp_file
            break

    if key_file:
        ssh_dir = os.path.expanduser("~/.ssh")
        ssh_key_path = os.path.join(ssh_dir, "nv_serving_inventory_crdb_prod")

        try:
            # Copy to SSH directory
            shutil.copy2(key_file, ssh_key_path)

            # Set proper permissions (600)
            os.chmod(ssh_key_path, 0o600)

            if debug:
                print(f"{Fore.GREEN}Private key copied to: {ssh_key_path}{Fore.RESET}")
                print(f"{Fore.CYAN}Permissions set to 600{Fore.RESET}")

            # Test the key - always show this header
            print(f"{Fore.YELLOW}=== Testing SSH Key ==={Fore.RESET}")
            test_result = subprocess.run(
                f'ssh-keygen -l -f "{ssh_key_path}"',
                shell=True,
                capture_output=True,
                text=True,
                check=False
            )

            if test_result.returncode == 0:
                if debug:
                    print(f"{Fore.GREEN}✓ Valid SSH private key{Fore.RESET}")
                    print(f"{Fore.CYAN}Key fingerprint:{Fore.RESET} {test_result.stdout.strip()}")
            else:
                if debug:
                    print(f"{Fore.YELLOW}Key validation output:{Fore.RESET} {test_result.stderr}")

        except Exception as e:
            if debug:
                print(f"{Fore.RED}Failed to copy key to SSH directory: {e}{Fore.RESET}")
    else:
        if debug:
            print(f"{Fore.RED}No downloaded key file found to copy{Fore.RESET}")

def main():
    parser = argparse.ArgumentParser(description="Retrieve and setup SSH private key from 1Password")
    parser.add_argument('-d', '--debug', action='store_true',
                       help='Enable debug mode for verbose output')

    args = parser.parse_args()

    get_private_key_file(debug=args.debug)
    # Always show this header
    print(f"\n{Fore.YELLOW}=== Setting up SSH key ==={Fore.RESET}")
    copy_key_to_ssh(debug=args.debug)

if __name__ == "__main__":
    main()