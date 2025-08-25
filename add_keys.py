#!/usr/bin/env python3

import json
import subprocess
import os
import glob
import shutil
import argparse
import re
from ddop import DDOP
from colorama import Fore

# Initialize 1Password client
op = DDOP(account="doordash.1password.com")

def transform_cluster_name_for_search(cluster_name):
    """
    Transform cluster name for 1Password search.
    Example: nv_serving_inventory-crdb-node-prod-usw2-doordash -> nv-serving-inventory crdb prod
    """
    # Remove the 'usw2-doordash' suffix
    transformed = re.sub(r'-usw2-doordash$', '', cluster_name)

    # Replace underscores with dashes in the first part
    if '_' in transformed:
        parts = transformed.split('-', 1)  # Split on first dash
        if len(parts) > 1:
            first_part = parts[0].replace('_', '-')
            remaining = parts[1]
            transformed = f"{first_part}-{remaining}"

    # Replace dashes with spaces in the '-crdb-node-prod' part
    transformed = re.sub(r'-crdb-node-prod', ' crdb prod', transformed)

    # Remove the word 'node' if it still exists
    transformed = re.sub(r'\bnode\b', '', transformed).strip()

    # Clean up any extra spaces
    transformed = re.sub(r'\s+', ' ', transformed)

    return transformed

def search_onepassword_item(search_term, debug=False):
    """
    Search for items in 1Password using the transformed cluster name.
    """
    vault_id = 'lfnuhv7jc72reknrdqlkup2ubm'  # crdb prod vault

    try:
        if debug:
            print(f"{Fore.CYAN}Searching for:{Fore.RESET} '{search_term}'")

        # Search for items containing the search term
        search_result = subprocess.run(
            f'op item list --vault {vault_id} --format=json',
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )

        items = json.loads(search_result.stdout)

        # Filter items that match our search term
        matching_items = []
        for item in items:
            title = item.get('title', '').lower()
            if search_term.lower() in title:
                matching_items.append(item)

        if debug:
            print(f"{Fore.CYAN}Found {len(matching_items)} matching items{Fore.RESET}")
            for item in matching_items:
                print(f"  - {item.get('title', 'Unknown')}")

        if len(matching_items) == 1:
            return matching_items[0]['title']
        elif len(matching_items) > 1:
            if debug:
                print(f"{Fore.YELLOW}Multiple items found, using first match{Fore.RESET}")
            return matching_items[0]['title']
        else:
            if debug:
                print(f"{Fore.RED}No matching items found{Fore.RESET}")
            return None

    except subprocess.CalledProcessError as e:
        if debug:
            print(f"{Fore.RED}Failed to search 1Password: {e}{Fore.RESET}")
            print(f"{Fore.RED}Error: {e.stderr}{Fore.RESET}")
        return None
    except Exception as e:
        if debug:
            print(f"{Fore.RED}Error searching 1Password: {e}{Fore.RESET}")
        return None

def get_ssh_key_passphrase(item_name, vault_id, debug=False):
    """
    Get the SSH key passphrase from the 1Password item.
    """
    try:
        if debug:
            print(f"{Fore.CYAN}Retrieving SSH key passphrase...{Fore.RESET}")

        passphrase_result = subprocess.run(
            f'op item get "{item_name}" --vault {vault_id} --fields label=ssh-key-passphrase --reveal',
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )

        passphrase = passphrase_result.stdout.strip()

        if passphrase:
            if debug:
                print(f"{Fore.GREEN}✓ SSH key passphrase retrieved{Fore.RESET}")
                print(f"{Fore.CYAN}Passphrase length:{Fore.RESET} {len(passphrase)} characters")

            # Always print the passphrase to screen
            print(f"{Fore.YELLOW}SSH Key Passphrase:{Fore.RESET} {passphrase}")
            return passphrase
        else:
            if debug:
                print(f"{Fore.YELLOW}SSH key passphrase is empty{Fore.RESET}")
            print(f"{Fore.YELLOW}No SSH key passphrase found{Fore.RESET}")
            return None

    except subprocess.CalledProcessError as e:
        if debug:
            print(f"{Fore.RED}Failed to get SSH key passphrase: {e}{Fore.RESET}")
            print(f"{Fore.RED}Error: {e.stderr}{Fore.RESET}")
        return None
    except Exception as e:
        if debug:
            print(f"{Fore.RED}Error retrieving SSH key passphrase: {e}{Fore.RESET}")
        return None

def get_private_key_file(cluster_name, debug=False):
    """
    Retrieve the private key file from 1Password.
    """
    vault_id = 'lfnuhv7jc72reknrdqlkup2ubm'  # crdb prod vault

    # Transform cluster name for search
    search_term = transform_cluster_name_for_search(cluster_name)

    # Always show this header
    print(f"{Fore.YELLOW}=== Retrieving 1Password Item Information ==={Fore.RESET}")

    if debug:
        print(f"{Fore.CYAN}Original cluster name:{Fore.RESET} {cluster_name}")
        print(f"{Fore.CYAN}Search term:{Fore.RESET} {search_term}")
        print(f"{Fore.CYAN}Vault ID:{Fore.RESET} {vault_id}")
        print()

    # Search for the item
    print(f"{Fore.GREEN}=== Searching for 1Password Item ==={Fore.RESET}")
    item_name = search_onepassword_item(search_term, debug)

    if not item_name:
        print(f"{Fore.RED}Could not find 1Password item for cluster: {cluster_name}{Fore.RESET}")
        return None, None

    if debug:
        print(f"{Fore.CYAN}Found item:{Fore.RESET} {item_name}")
        print()

    # Get SSH key passphrase
    passphrase = get_ssh_key_passphrase(item_name, vault_id, debug)

    try:
        # Always show this header
        print(f"{Fore.GREEN}=== Getting Item Details ==={Fore.RESET}")

        result = subprocess.run(
            f'op item get "{item_name}" --vault {vault_id} --format=json',
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

                    output_filename = f"/tmp/{cluster_name}"

                    # Use op read command which works
                    read_result = subprocess.run(
                        f'op read "op://{vault_id}/{item_name}/{file_name}" --out-file "{output_filename}"',
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

                        return output_filename, passphrase

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

    except subprocess.CalledProcessError as e:
        if debug:
            print(f"{Fore.RED}Failed to get item details: {e}{Fore.RESET}")
            print(f"{Fore.RED}Error: {e.stderr}{Fore.RESET}")
    except Exception as e:
        if debug:
            print(f"{Fore.RED}Error retrieving private key file: {e}{Fore.RESET}")

    return None, passphrase

def add_key_to_ssh_agent(ssh_key_path, passphrase=None, debug=False):
    """
    Add the private key to ssh-agent using the passphrase.
    """
    print(f"{Fore.YELLOW}=== Adding Key to SSH Agent ==={Fore.RESET}")

    try:
        if passphrase:
            # Use expect to provide the passphrase automatically
            expect_script = f'''
expect -c "
spawn ssh-add {ssh_key_path}
expect \\"Enter passphrase\\"
send \\"{passphrase}\\r\\"
expect eof
"
'''
            if debug:
                print(f"{Fore.CYAN}Adding key with passphrase using expect{Fore.RESET}")

            result = subprocess.run(
                expect_script,
                shell=True,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                print(f"{Fore.GREEN}✓ SSH key successfully added to ssh-agent{Fore.RESET}")
                if debug:
                    print(f"{Fore.CYAN}ssh-add output:{Fore.RESET} {result.stdout}")
            else:
                if debug:
                    print(f"{Fore.RED}Failed to add key to ssh-agent{Fore.RESET}")
                    print(f"{Fore.RED}Error output:{Fore.RESET} {result.stderr}")

                # Fallback: try without expect (user will need to enter passphrase manually)
                print(f"{Fore.YELLOW}Falling back to manual passphrase entry...{Fore.RESET}")
                manual_result = subprocess.run(
                    f'ssh-add "{ssh_key_path}"',
                    shell=True,
                    check=False
                )

                if manual_result.returncode == 0:
                    print(f"{Fore.GREEN}✓ SSH key successfully added to ssh-agent{Fore.RESET}")
                else:
                    print(f"{Fore.RED}Failed to add key to ssh-agent{Fore.RESET}")
        else:
            # No passphrase, add directly
            if debug:
                print(f"{Fore.CYAN}Adding key without passphrase{Fore.RESET}")

            result = subprocess.run(
                f'ssh-add "{ssh_key_path}"',
                shell=True,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                print(f"{Fore.GREEN}✓ SSH key successfully added to ssh-agent{Fore.RESET}")
                if debug:
                    print(f"{Fore.CYAN}ssh-add output:{Fore.RESET} {result.stdout}")
            else:
                if debug:
                    print(f"{Fore.RED}Failed to add key to ssh-agent{Fore.RESET}")
                    print(f"{Fore.RED}Error output:{Fore.RESET} {result.stderr}")

    except Exception as e:
        if debug:
            print(f"{Fore.RED}Error adding key to ssh-agent: {e}{Fore.RESET}")

def copy_key_to_ssh(cluster_name, passphrase=None, debug=False):
    """
    Copy the downloaded private key to SSH directory with proper permissions.
    """
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
        # Create a sanitized filename from cluster_name
        ssh_key_name = cluster_name.replace('-', '_')
        ssh_key_path = os.path.join(ssh_dir, ssh_key_name)

        try:
            # Copy to SSH directory
            shutil.copy2(key_file, ssh_key_path)

            # Set proper permissions (600)
            os.chmod(ssh_key_path, 0o600)

            if debug:
                print(f"{Fore.GREEN}Private key copied to: {ssh_key_path}{Fore.RESET}")
                print(f"{Fore.CYAN}Permissions set to 600{Fore.RESET}")
                if passphrase:
                    print(f"{Fore.CYAN}SSH key has passphrase:{Fore.RESET} Yes")
                else:
                    print(f"{Fore.CYAN}SSH key has passphrase:{Fore.RESET} No")

            # Test the key - always show this header
            print(f"{Fore.YELLOW}=== Testing SSH Key ==={Fore.RESET}")

            # If there's a passphrase, we need to test differently
            if passphrase:
                # Test with passphrase using ssh-keygen
                test_result = subprocess.run(
                    f'ssh-keygen -l -f "{ssh_key_path}" -P "{passphrase}"',
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=False
                )
            else:
                # Test without passphrase
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

                # Add the key to ssh-agent
                add_key_to_ssh_agent(ssh_key_path, passphrase, debug)
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
    parser.add_argument('-c', '--cluster', required=True,
                       help='Cluster name to retrieve the private key for')
    parser.add_argument('-d', '--debug', action='store_true',
                       help='Enable debug mode for verbose output')

    args = parser.parse_args()

    key_file, passphrase = get_private_key_file(args.cluster, debug=args.debug)

    # Always show this header
    print(f"\n{Fore.YELLOW}=== Setting up SSH key ==={Fore.RESET}")
    copy_key_to_ssh(args.cluster, passphrase=passphrase, debug=args.debug)

if __name__ == "__main__":
    main()