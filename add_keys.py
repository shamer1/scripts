#!/usr/bin/env python3

import json
import subprocess
import os
import glob
import shutil
import argparse
import re
import atexit
from ddop import DDOP
from colorama import Fore

# Global variable to track temp directory
TEMP_KEY_DIR = "/tmp/keys"

class OnePasswordCache:
    """Cache for 1Password operations to reduce API calls"""
    def __init__(self, account, vault_id):
        self.account = account
        self.vault_id = vault_id
        self._items_cache = None
        self._item_details_cache = {}

    def get_all_items(self, debug=False):
        """Get all items from vault with caching"""
        if self._items_cache is None:
            if debug:
                print(f"{Fore.CYAN}Fetching all vault items (cached)...{Fore.RESET}")

            result = subprocess.run(
                f'op item list --vault {self.vault_id} --format=json',
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )
            self._items_cache = json.loads(result.stdout)

        return self._items_cache

    def get_item_details(self, item_name, debug=False):
        """Get item details with caching"""
        if item_name not in self._item_details_cache:
            if debug:
                print(f"{Fore.CYAN}Fetching details for: {item_name}{Fore.RESET}")

            result = subprocess.run(
                f'op item get "{item_name}" --vault {self.vault_id} --format=json',
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )
            self._item_details_cache[item_name] = json.loads(result.stdout)

        return self._item_details_cache[item_name]

def setup_temp_directory():
    """Create and setup temporary key directory"""
    if not os.path.exists(TEMP_KEY_DIR):
        os.makedirs(TEMP_KEY_DIR, mode=0o700)  # Secure permissions

    # Register cleanup function to run at exit
    atexit.register(cleanup_temp_keys)

def cleanup_temp_keys(debug=False):
    """Securely cleanup temporary keys"""
    if not os.path.exists(TEMP_KEY_DIR):
        return

    if debug:
        print(f"\n{Fore.YELLOW}=== Cleaning up temporary keys ==={Fore.RESET}")

    try:
        # Find all files in the temp directory
        key_files = glob.glob(os.path.join(TEMP_KEY_DIR, "*"))

        for key_file in key_files:
            if os.path.isfile(key_file):
                try:
                    # Shred the file (overwrite with random data)
                    if debug:
                        print(f"{Fore.CYAN}Shredding: {key_file}{Fore.RESET}")

                    # Use shred command if available, otherwise use dd
                    shred_result = subprocess.run(
                        f'shred -vfz -n 3 "{key_file}"',
                        shell=True,
                        capture_output=True,
                        text=True,
                        check=False
                    )

                    if shred_result.returncode != 0:
                        # Fallback to dd if shred is not available
                        if debug:
                            print(f"{Fore.YELLOW}Shred failed, using dd fallback{Fore.RESET}")

                        file_size = os.path.getsize(key_file)
                        subprocess.run(
                            f'dd if=/dev/urandom of="{key_file}" bs={file_size} count=1 conv=notrunc 2>/dev/null',
                            shell=True,
                            check=False
                        )

                    # Remove the file
                    os.remove(key_file)

                    if debug:
                        print(f"{Fore.GREEN}✓ Cleaned: {os.path.basename(key_file)}{Fore.RESET}")

                except Exception as e:
                    if debug:
                        print(f"{Fore.RED}Error cleaning {key_file}: {e}{Fore.RESET}")

        # Remove the directory
        try:
            os.rmdir(TEMP_KEY_DIR)
            if debug:
                print(f"{Fore.GREEN}✓ Removed temp directory: {TEMP_KEY_DIR}{Fore.RESET}")
        except:
            if debug:
                print(f"{Fore.YELLOW}Could not remove temp directory (may not be empty){Fore.RESET}")

    except Exception as e:
        if debug:
            print(f"{Fore.RED}Error during cleanup: {e}{Fore.RESET}")

def transform_cluster_name_for_search(cluster_name):
    """Transform cluster name for 1Password search."""
    transformed = re.sub(r'-usw2-doordash$', '', cluster_name)

    if '_' in transformed:
        parts = transformed.split('-', 1)
        if len(parts) > 1:
            first_part = parts[0].replace('_', '-')
            remaining = parts[1]
            transformed = f"{first_part}-{remaining}"

    transformed = re.sub(r'-crdb-node-prod', ' crdb prod', transformed)
    transformed = re.sub(r'\bnode\b', '', transformed).strip()
    transformed = re.sub(r'\s+', ' ', transformed)

    return transformed

def find_all_cluster_items_fast(cache, debug=False):
    """Fast version using cached data"""
    items = cache.get_all_items(debug)

    matching_clusters = []
    pattern = re.compile(r'.*-crdb-node-prod-usw2-doordash$', re.IGNORECASE)

    for item in items:
        title = item.get('title', '')
        if pattern.match(title):
            matching_clusters.append(title)

    if debug:
        print(f"{Fore.CYAN}Found {len(matching_clusters)} matching cluster items{Fore.RESET}")

    return matching_clusters

def find_item_by_search_term(cache, search_term, debug=False):
    """Fast search using cached data"""
    items = cache.get_all_items(debug)

    matching_items = []
    for item in items:
        title = item.get('title', '').lower()
        if search_term.lower() in title:
            matching_items.append(item)

    if matching_items:
        return matching_items[0]['title']
    return None

def get_ssh_key_passphrase_fast(item_name, vault_id, debug=False):
    """Fast passphrase retrieval"""
    try:
        result = subprocess.run(
            f'op item get "{item_name}" --vault {vault_id} --fields label=ssh-key-passphrase --reveal',
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )

        passphrase = result.stdout.strip()
        if passphrase:
            if debug:
                print(f"{Fore.CYAN}✓ SSH key passphrase retrieved{Fore.RESET}")
            return passphrase
        return None
    except:
        return None

def download_private_key_fast(item_name, cluster_name, vault_id, debug=False):
    """Fast download using direct op read"""
    try:
        # Try to find a file attachment first
        result = subprocess.run(
            f'op item get "{item_name}" --vault {vault_id} --format=json',
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )

        item_json = json.loads(result.stdout)

        if 'files' in item_json and item_json['files']:
            file_info = item_json['files'][0]  # Take first file
            file_name = file_info.get('name', 'Unknown')

            output_filename = os.path.join(TEMP_KEY_DIR, cluster_name)

            result = subprocess.run(
                f'op read "op://{vault_id}/{item_name}/{file_name}" --out-file "{output_filename}"',
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )

            if os.path.exists(output_filename):
                # Set secure permissions on the downloaded key
                os.chmod(output_filename, 0o600)
                return output_filename

        return None
    except:
        return None

def process_cluster_fast(cluster_name, cache, vault_id, debug=False):
    """Fast cluster processing"""
    if debug:
        print(f"\n{Fore.MAGENTA}Processing: {cluster_name}{Fore.RESET}")

    search_term = transform_cluster_name_for_search(cluster_name)

    # Try transformed name first
    item_name = find_item_by_search_term(cache, search_term, debug)
    passphrase = None
    key_file = None

    if item_name:
        passphrase = get_ssh_key_passphrase_fast(item_name, vault_id, debug)
        key_file = download_private_key_fast(item_name, cluster_name, vault_id, debug)

    # If no file found, try original name
    if not key_file:
        original_item = find_item_by_search_term(cache, cluster_name, debug)
        if original_item and original_item != item_name:
            if not passphrase:
                passphrase = get_ssh_key_passphrase_fast(original_item, vault_id, debug)
            key_file = download_private_key_fast(original_item, cluster_name, vault_id, debug)

    if key_file:
        return setup_ssh_key_fast(cluster_name, key_file, passphrase, debug)

    return False

def setup_ssh_key_fast(cluster_name, key_file, passphrase, debug=False):
    """Fast SSH key setup"""
    ssh_dir = os.path.expanduser("~/.ssh")
    ssh_key_name = cluster_name.replace('-', '_')
    ssh_key_path = os.path.join(ssh_dir, ssh_key_name)

    try:
        # Copy and set permissions
        shutil.copy2(key_file, ssh_key_path)
        os.chmod(ssh_key_path, 0o600)

        # Add to ssh-agent
        if passphrase:
            expect_script = f'''expect -c "spawn ssh-add {ssh_key_path}; expect \\"Enter passphrase\\"; send \\"{passphrase}\\r\\"; expect eof"'''
            result = subprocess.run(expect_script, shell=True, capture_output=True, check=False)
        else:
            result = subprocess.run(f'ssh-add "{ssh_key_path}"', shell=True, capture_output=True, check=False)

        if result.returncode == 0:
            if debug:
                print(f"{Fore.GREEN}✓ {cluster_name} added to ssh-agent{Fore.RESET}")
            else:
                print(f"{Fore.GREEN}✓ {cluster_name}{Fore.RESET}")
            return True
        else:
            if debug:
                print(f"{Fore.RED}✗ {cluster_name} failed to add to ssh-agent{Fore.RESET}")
                if result.stderr:
                    print(f"{Fore.RED}Error: {result.stderr.decode() if isinstance(result.stderr, bytes) else result.stderr}{Fore.RESET}")
            else:
                print(f"{Fore.RED}✗ {cluster_name}{Fore.RESET}")
            return False

    except Exception as e:
        if debug:
            print(f"{Fore.RED}Error processing {cluster_name}: {e}{Fore.RESET}")
        return False

def process_all_clusters_fast(account, debug=False):
    """Fast processing of all clusters"""
    vault_id = 'lfnuhv7jc72reknrdqlkup2ubm'
    cache = OnePasswordCache(account, vault_id)

    print(f"{Fore.YELLOW}Finding all cluster items...{Fore.RESET}")
    clusters = find_all_cluster_items_fast(cache, debug)

    if not clusters:
        print(f"{Fore.RED}No clusters found{Fore.RESET}")
        return

    print(f"{Fore.GREEN}Found {len(clusters)} clusters. Processing...{Fore.RESET}")

    successful = 0
    failed = 0

    for cluster in clusters:
        try:
            if process_cluster_fast(cluster, cache, vault_id, debug):
                successful += 1
            else:
                failed += 1
        except Exception as e:
            if debug:
                print(f"{Fore.RED}Error processing {cluster}: {e}{Fore.RESET}")
            failed += 1

    print(f"\n{Fore.GREEN}Success: {successful}{Fore.RESET} | {Fore.RED}Failed: {failed}{Fore.RESET}")

def main():
    parser = argparse.ArgumentParser(description="Fast SSH key retrieval from 1Password")
    parser.add_argument('-c', '--cluster', help='Single cluster name')
    parser.add_argument('-a', '--account', default='doordash.1password.com', help='1Password account')
    parser.add_argument('--add-all', action='store_true', help='Add all matching keys')
    parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')
    parser.add_argument('--fast', action='store_true', default=True, help='Use fast mode (default)')

    args = parser.parse_args()

    if args.add_all and args.cluster:
        print(f"{Fore.RED}Error: Cannot specify both --cluster and --add-all{Fore.RESET}")
        return

    if not args.add_all and not args.cluster:
        print(f"{Fore.RED}Error: Must specify either --cluster or --add-all{Fore.RESET}")
        return

    # Setup secure temporary directory
    setup_temp_directory()

    vault_id = 'lfnuhv7jc72reknrdqlkup2ubm'

    try:
        if args.add_all:
            process_all_clusters_fast(args.account, args.debug)
        else:
            cache = OnePasswordCache(args.account, vault_id)
            success = process_cluster_fast(args.cluster, cache, vault_id, args.debug)
            if success:
                print(f"{Fore.GREEN}✓ Successfully processed {args.cluster}{Fore.RESET}")
            else:
                print(f"{Fore.RED}✗ Failed to process {args.cluster}{Fore.RESET}")
    finally:
        # Explicit cleanup (also registered with atexit as backup)
        if args.debug:
            cleanup_temp_keys(debug=True)
        else:
            cleanup_temp_keys(debug=False)

if __name__ == "__main__":
    main()