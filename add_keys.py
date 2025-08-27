#!/usr/bin/env python3

import json
import subprocess
import os
import glob
import shutil
import argparse
import re
import atexit
import concurrent.futures
import threading
import tempfile
from collections import defaultdict
from ddop import DDOP
from colorama import Fore

# Global variable to track temp directory
TEMP_KEY_DIR = "/tmp/keys"

class OnePasswordCache:
    """Optimized cache for 1Password operations"""
    def __init__(self, account, vault_id):
        self.account = account
        self.vault_id = vault_id
        self._items_cache = None
        self._item_details_cache = {}
        self._title_to_item_map = {}
        self._lock = threading.Lock()

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
            items = json.loads(result.stdout)
            self._items_cache = items

            # Build title-to-item mapping for faster lookups
            for item in items:
                title = item.get('title', '').lower()
                self._title_to_item_map[title] = item

        return self._items_cache

    def find_item_by_search_term_fast(self, search_term):
        """Ultra-fast search using pre-built mapping"""
        if not self._title_to_item_map:
            self.get_all_items()

        search_lower = search_term.lower()

        # Direct match first
        if search_lower in self._title_to_item_map:
            return self._title_to_item_map[search_lower]['title']

        # Substring search
        for title, item in self._title_to_item_map.items():
            if search_lower in title:
                return item['title']

        return None

    def batch_get_item_details(self, item_names, debug=False):
        """Batch fetch item details with threading"""
        with self._lock:
            uncached_items = [name for name in item_names if name not in self._item_details_cache]

        if uncached_items and len(uncached_items) > 1:
            # Use threading for batch operations
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                futures = {executor.submit(self._fetch_single_item, item_name): item_name
                          for item_name in uncached_items}

                for future in concurrent.futures.as_completed(futures):
                    item_name = futures[future]
                    try:
                        result = future.result()
                        if result:
                            with self._lock:
                                self._item_details_cache[item_name] = result
                    except Exception as e:
                        if debug:
                            print(f"{Fore.RED}Error fetching {item_name}: {e}{Fore.RESET}")

        elif uncached_items:
            # Single item
            for item_name in uncached_items:
                result = self._fetch_single_item(item_name)
                if result:
                    self._item_details_cache[item_name] = result

        return {name: self._item_details_cache.get(name) for name in item_names}

    def _fetch_single_item(self, item_name):
        """Fetch single item details"""
        try:
            result = subprocess.run(
                f'op item get "{item_name}" --vault {self.vault_id} --format=json',
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
        except:
            return None

def clean_temp_directory(debug=False):
    """Clean the temp directory before starting"""
    if os.path.exists(TEMP_KEY_DIR):
        if debug:
            print(f"{Fore.YELLOW}Cleaning existing temp directory: {TEMP_KEY_DIR}{Fore.RESET}")

        try:
            # Get list of files
            key_files = glob.glob(os.path.join(TEMP_KEY_DIR, "*"))

            if key_files:
                if debug:
                    print(f"{Fore.CYAN}Found {len(key_files)} existing files to remove{Fore.RESET}")

                for key_file in key_files:
                    if os.path.isfile(key_file):
                        try:
                            if debug:
                                print(f"{Fore.CYAN}Removing: {os.path.basename(key_file)}{Fore.RESET}")

                            # Secure removal - overwrite then delete
                            with open(key_file, 'r+b') as f:
                                length = f.seek(0, 2)  # Get file size
                                f.seek(0)
                                f.write(os.urandom(length))  # Overwrite with random data
                                f.flush()
                                os.fsync(f.fileno())

                            os.remove(key_file)

                            if debug:
                                print(f"{Fore.GREEN}✓ Removed: {os.path.basename(key_file)}{Fore.RESET}")

                        except Exception as e:
                            if debug:
                                print(f"{Fore.RED}Error removing {key_file}: {e}{Fore.RESET}")
                            # Try simple removal if secure removal fails
                            try:
                                os.remove(key_file)
                            except:
                                pass

                if debug:
                    print(f"{Fore.GREEN}✓ Temp directory cleaned{Fore.RESET}")
            else:
                if debug:
                    print(f"{Fore.CYAN}Temp directory is already empty{Fore.RESET}")

        except Exception as e:
            if debug:
                print(f"{Fore.RED}Error cleaning temp directory: {e}{Fore.RESET}")
            # If we can't clean it, try to remove and recreate
            try:
                shutil.rmtree(TEMP_KEY_DIR)
                if debug:
                    print(f"{Fore.YELLOW}Removed entire temp directory{Fore.RESET}")
            except:
                pass

def setup_temp_directory(debug=False):
    """Create and setup temporary key directory"""
    # First clean any existing files
    clean_temp_directory(debug)

    # Create directory if it doesn't exist
    if not os.path.exists(TEMP_KEY_DIR):
        os.makedirs(TEMP_KEY_DIR, mode=0o700)
        if debug:
            print(f"{Fore.GREEN}Created temp directory: {TEMP_KEY_DIR}{Fore.RESET}")

    # Register cleanup function to run at exit
    atexit.register(cleanup_temp_keys)

def cleanup_temp_keys(debug=False):
    """Simple sequential cleanup to avoid threading issues"""
    if not os.path.exists(TEMP_KEY_DIR):
        return

    if debug:
        print(f"\n{Fore.YELLOW}=== Final cleanup of temporary keys ==={Fore.RESET}")

    try:
        key_files = glob.glob(os.path.join(TEMP_KEY_DIR, "*"))

        for key_file in key_files:
            if os.path.isfile(key_file):
                try:
                    if debug:
                        print(f"{Fore.CYAN}Removing: {os.path.basename(key_file)}{Fore.RESET}")

                    # Simple secure removal - overwrite then delete
                    with open(key_file, 'r+b') as f:
                        length = f.seek(0, 2)  # Get file size
                        f.seek(0)
                        f.write(os.urandom(length))  # Overwrite with random data
                        f.flush()
                        os.fsync(f.fileno())

                    os.remove(key_file)

                    if debug:
                        print(f"{Fore.GREEN}✓ Cleaned: {os.path.basename(key_file)}{Fore.RESET}")

                except Exception as e:
                    if debug:
                        print(f"{Fore.RED}Error cleaning {key_file}: {e}{Fore.RESET}")

        # Remove directory
        try:
            os.rmdir(TEMP_KEY_DIR)
            if debug:
                print(f"{Fore.GREEN}✓ Removed temp directory{Fore.RESET}")
        except:
            pass

    except Exception as e:
        if debug:
            print(f"{Fore.RED}Cleanup error: {e}{Fore.RESET}")

def transform_cluster_name_for_search(cluster_name):
    """Optimized transform with compiled regex"""
    # Use pre-compiled patterns for speed
    if not hasattr(transform_cluster_name_for_search, '_patterns'):
        transform_cluster_name_for_search._patterns = {
            'suffix': re.compile(r'-usw2-doordash$'),
            'crdb': re.compile(r'-crdb-node-prod'),
            'node': re.compile(r'\bnode\b'),
            'spaces': re.compile(r'\s+')
        }

    patterns = transform_cluster_name_for_search._patterns

    transformed = patterns['suffix'].sub('', cluster_name)

    if '_' in transformed:
        parts = transformed.split('-', 1)
        if len(parts) > 1:
            first_part = parts[0].replace('_', '-')
            remaining = parts[1]
            transformed = f"{first_part}-{remaining}"

    transformed = patterns['crdb'].sub(' crdb prod', transformed)
    transformed = patterns['node'].sub('', transformed).strip()
    transformed = patterns['spaces'].sub(' ', transformed)

    return transformed

def transform_cluster_name_for_passphrase_search(cluster_name):
    """Transform cluster name specifically to find passphrase items"""
    # Remove the full suffix first
    base_name = cluster_name.replace('-crdb-node-prod-usw2-doordash', '')

    # Also handle the short suffix
    base_name = base_name.replace('-crdb-node-prod', '')

    # Convert underscores to hyphens for consistent search
    base_name = base_name.replace('_', '-')

    # Transform to the passphrase format: "base-name crdb prod"
    passphrase_name = f"{base_name} crdb prod"

    return passphrase_name

def find_all_cluster_items_ultra_fast(cache, debug=False):
    """Ultra-fast search using pre-compiled regex - now includes both patterns"""
    items = cache.get_all_items()

    # Pre-compiled patterns
    if not hasattr(find_all_cluster_items_ultra_fast, '_patterns'):
        find_all_cluster_items_ultra_fast._patterns = {
            'full_pattern': re.compile(r'.*-crdb-node-prod-usw2-doordash$', re.IGNORECASE),
            'short_pattern': re.compile(r'.*-crdb-node-prod$', re.IGNORECASE)
        }

    patterns = find_all_cluster_items_ultra_fast._patterns
    matching_items = []

    for item in items:
        title = item.get('title', '')
        # Check both patterns
        if patterns['full_pattern'].match(title) or patterns['short_pattern'].match(title):
            matching_items.append(title)

    if debug:
        print(f"{Fore.CYAN}Found {len(matching_items)} items matching CRDB patterns{Fore.RESET}")
        # Show breakdown by pattern
        full_matches = [title for title in matching_items if patterns['full_pattern'].match(title)]
        short_matches = [title for title in matching_items if patterns['short_pattern'].match(title)]
        print(f"{Fore.CYAN}  - Full pattern (*-crdb-node-prod-usw2-doordash): {len(full_matches)}{Fore.RESET}")
        print(f"{Fore.CYAN}  - Short pattern (*-crdb-node-prod): {len(short_matches)}{Fore.RESET}")

    return matching_items

def find_item_by_cluster_name(cache, cluster_name, debug=False):
    """Find 1Password item for a specific cluster name using multiple search strategies"""
    search_candidates = []

    # Strategy 1: Exact cluster name
    search_candidates.append(cluster_name)

    # Strategy 2: Transformed search term
    transformed = transform_cluster_name_for_search(cluster_name)
    if transformed != cluster_name:
        search_candidates.append(transformed)

    # Strategy 3: Add different suffix patterns
    base_name = cluster_name.replace('-crdb-node-prod-usw2-doordash', '').replace('-crdb-node-prod', '')
    search_candidates.extend([
        f"{base_name}-crdb-node-prod-usw2-doordash",
        f"{base_name}-crdb-node-prod",
        base_name
    ])

    if debug:
        print(f"{Fore.CYAN}Searching for cluster '{cluster_name}' using candidates:{Fore.RESET}")
        for i, candidate in enumerate(search_candidates, 1):
            print(f"  {i}. {candidate}")

    # Try each search candidate
    for candidate in search_candidates:
        item_name = cache.find_item_by_search_term_fast(candidate)
        if item_name:
            if debug:
                print(f"{Fore.GREEN}✓ Found item: {item_name} (using search: {candidate}){Fore.RESET}")
            return item_name

    if debug:
        print(f"{Fore.RED}✗ No item found for cluster: {cluster_name}{Fore.RESET}")

    return None

def find_passphrase_item_for_cluster(cache, cluster_name, debug=False):
    """Find the 1Password item that contains the SSH key passphrase for a cluster"""
    # Transform cluster name to passphrase item format
    passphrase_search_term = transform_cluster_name_for_passphrase_search(cluster_name)

    if debug:
        print(f"{Fore.CYAN}Searching for passphrase item for '{cluster_name}' using: '{passphrase_search_term}'{Fore.RESET}")

    # Try to find the passphrase item
    passphrase_item = cache.find_item_by_search_term_fast(passphrase_search_term)

    # Filter out .pub items AND items that contain the cluster name (those are key files, not passphrase items)
    if passphrase_item and not passphrase_item.lower().endswith('.pub') and cluster_name not in passphrase_item:
        if debug:
            print(f"{Fore.GREEN}✓ Found passphrase item: {passphrase_item}{Fore.RESET}")
        return passphrase_item
    elif passphrase_item and passphrase_item.lower().endswith('.pub'):
        if debug:
            print(f"{Fore.YELLOW}⚠ Skipping .pub item (no passphrase): {passphrase_item}{Fore.RESET}")
    elif passphrase_item and cluster_name in passphrase_item:
        if debug:
            print(f"{Fore.YELLOW}⚠ Skipping key file item (contains cluster name): {passphrase_item}{Fore.RESET}")

    # Fallback: try variations with both underscores and hyphens
    base_name = cluster_name.replace('-crdb-node-prod-usw2-doordash', '').replace('-crdb-node-prod', '')

    # Create variations with both underscores and hyphens
    base_name_with_hyphens = base_name.replace('_', '-')
    base_name_with_underscores = base_name.replace('-', '_')

    fallback_candidates = [
        # Primary variations with hyphens (most common)
        f"{base_name_with_hyphens} crdb prod",
        f"{base_name_with_hyphens}-crdb-prod",
        f"{base_name_with_hyphens} crdb",

        # Variations with underscores (less common but possible)
        f"{base_name_with_underscores} crdb prod",
        f"{base_name_with_underscores}-crdb-prod",
        f"{base_name_with_underscores} crdb",

        # Mixed variations
        f"{base_name_with_hyphens}_crdb_prod",
        f"{base_name_with_underscores}-crdb-prod",

        # Original base names
        base_name_with_hyphens,
        base_name_with_underscores,
        base_name  # Original unchanged
    ]

    # Remove duplicates while preserving order
    seen = set()
    unique_candidates = []
    for candidate in fallback_candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique_candidates.append(candidate)

    if debug:
        print(f"{Fore.CYAN}Trying {len(unique_candidates)} fallback passphrase searches:{Fore.RESET}")

    for candidate in unique_candidates:
        if debug:
            print(f"  - {candidate}")
        item = cache.find_item_by_search_term_fast(candidate)

        # Filter out .pub items AND items that contain the cluster name
        if item and not item.lower().endswith('.pub') and cluster_name not in item:
            if debug:
                print(f"{Fore.GREEN}✓ Found passphrase item via fallback: {item}{Fore.RESET}")
            return item
        elif item and item.lower().endswith('.pub'):
            if debug:
                print(f"{Fore.YELLOW}⚠ Skipping .pub item (fallback): {item}{Fore.RESET}")
        elif item and cluster_name in item:
            if debug:
                print(f"{Fore.YELLOW}⚠ Skipping key file item (fallback, contains cluster name): {item}{Fore.RESET}")

    if debug:
        print(f"{Fore.RED}✗ No passphrase item found for cluster: {cluster_name}{Fore.RESET}")

    return None

def find_item_by_search_term_exact_match_only(cache, search_term):
    """Find items by exact match only (no substring search)"""
    if not cache._title_to_item_map:
        cache.get_all_items()

    search_lower = search_term.lower()

    # Only direct match
    if search_lower in cache._title_to_item_map:
        return cache._title_to_item_map[search_lower]['title']

    return None

def find_passphrase_item_for_cluster_improved(cache, cluster_name, debug=False):
    """Improved passphrase search that prioritizes exact matches and handles complex naming patterns"""

    if debug:
        print(f"{Fore.CYAN}=== Processing passphrase search for: {cluster_name} ==={Fore.RESET}")

    # Handle complex naming patterns first
    base_service_name = None

    # Pattern 1: "service-crdb Prod - service-crdb-node-prod" -> "service"
    # Example: "lx-hub-crdb Prod - lx-hub-crdb-node-prod" -> "lx-hub"
    match = re.match(r'^(.+?)-crdb\s+Prod\s+-\s+\1-crdb-node-prod', cluster_name)
    if match:
        base_service_name = match.group(1)
        if debug:
            print(f"{Fore.CYAN}Pattern 1 matched: extracted '{base_service_name}' from complex pattern{Fore.RESET}")

    # Pattern 2: "service crdb prod - service-crdb-node-prod" -> "service"
    if not base_service_name:
        match = re.match(r'^(.+?)\s+crdb\s+prod\s+-\s+.+-crdb-node-prod', cluster_name)
        if match:
            base_service_name = match.group(1)
            if debug:
                print(f"{Fore.CYAN}Pattern 2 matched: extracted '{base_service_name}'{Fore.RESET}")

    # Pattern 3: "service_name-crdb prod - service_name-crdb-node-prod" -> "service-name"
    # Example: "doordash_api_gateway-crdb prod - doordash_api_gateway-crdb-node-prod" -> "doordash-api-gateway"
    if not base_service_name:
        match = re.match(r'^(.+?)-crdb\s+prod\s+-\s+\1-crdb-node-prod', cluster_name)
        if match:
            base_service_name = match.group(1).replace('_', '-')  # Convert underscores to hyphens
            if debug:
                print(f"{Fore.CYAN}Pattern 3 matched: extracted '{base_service_name}' (converted underscores to hyphens){Fore.RESET}")

    # Pattern 4: Handle mixed underscore/hyphen patterns
    # Example: "doordash_api_gateway-crdb prod - doordash_api_gateway-crdb-node-prod" -> try "doordash-api-gateway"
    if not base_service_name:
        match = re.match(r'^(.+?)[-_]crdb\s+prod\s+-\s+(.+?)[-_]crdb-node-prod', cluster_name)
        if match:
            service_part1 = match.group(1)
            service_part2 = match.group(2)
            # Use the first part but normalize it
            base_service_name = service_part1.replace('_', '-')
            if debug:
                print(f"{Fore.CYAN}Pattern 4 matched: extracted '{base_service_name}' from mixed pattern{Fore.RESET}")

    # Pattern 5: "crdb service prod - service-crdb-node-prod" -> "service"
    # Example: "crdb photo-service prod - photo-service-crdb-node-prod" -> "photo-service"
    if not base_service_name:
        match = re.match(r'^crdb\s+(.+?)\s+prod\s+-\s+\1-crdb-node-prod', cluster_name)
        if match:
            base_service_name = match.group(1)
            if debug:
                print(f"{Fore.CYAN}Pattern 5 matched: extracted '{base_service_name}' from crdb-prefix pattern{Fore.RESET}")

    # Pattern 6: "service crdb - Prod - service-crdb-node-prod" -> "service"
    # Example: "geo crdb - Prod - geo-crdb-node-prod" -> "geo"
    if not base_service_name:
        match = re.match(r'^(.+?)\s+crdb\s+-\s+Prod\s+-\s+\1-crdb-node-prod', cluster_name)
        if match:
            base_service_name = match.group(1)
            if debug:
                print(f"{Fore.CYAN}Pattern 6 matched: extracted '{base_service_name}' from crdb-Prod pattern{Fore.RESET}")

    # Pattern 7: "service-name prod - transformed_service_name-crdb-node-prod" -> handle complex transformations
    # Example: "merchant-financial-service prod - merchant_finance_service-crdb-node-prod" -> "merchant-financial-svc"
    if not base_service_name:
        match = re.match(r'^(.+?)\s+prod\s+-\s+(.+?)-crdb-node-prod', cluster_name)
        if match:
            original_service = match.group(1)
            transformed_service = match.group(2)

            # Try various transformations of the original service name
            candidates_to_try = []

            # 1. Try the original service name as-is
            candidates_to_try.append(original_service)

            # 2. Try abbreviating "service" to "svc"
            if 'service' in original_service:
                candidates_to_try.append(original_service.replace('service', 'svc'))
                candidates_to_try.append(original_service.replace('-service', '-svc'))

            # 3. Try the transformed service name converted back to hyphens
            transformed_with_hyphens = transformed_service.replace('_', '-')
            candidates_to_try.append(transformed_with_hyphens)

            # 4. Try abbreviated version of transformed name
            if 'service' in transformed_with_hyphens:
                candidates_to_try.append(transformed_with_hyphens.replace('service', 'svc'))
                candidates_to_try.append(transformed_with_hyphens.replace('-service', '-svc'))

            # Test each candidate to see if it exists in the cache
            for candidate in candidates_to_try:
                test_passphrase_name = f"{candidate} crdb prod"
                # Quick check if this item exists
                if cache.find_item_by_search_term_fast(test_passphrase_name):
                    base_service_name = candidate
                    if debug:
                        print(f"{Fore.CYAN}Pattern 7 matched: found '{base_service_name}' for complex transformation{Fore.RESET}")
                    break

    # If we found a base service name from patterns, use it
    if base_service_name:
        # Generate primary candidates based on extracted service name
        primary_candidates = [
            f"{base_service_name} crdb prod",
            f"{base_service_name.replace('-', '_')} crdb prod",  # Try with underscores too
            f"{base_service_name} crdb",
            f"{base_service_name.replace('-', '_')} crdb"
        ]

        if debug:
            print(f"{Fore.CYAN}Using pattern-based candidates for '{base_service_name}':{Fore.RESET}")
            for candidate in primary_candidates:
                print(f"  - {candidate}")

        # Try pattern-based candidates first
        for candidate in primary_candidates:
            # Try exact match first
            item = find_item_by_search_term_exact_match_only(cache, candidate)
            if item and not item.lower().endswith('.pub') and cluster_name not in item:
                if debug:
                    print(f"{Fore.GREEN}✓ Found passphrase item (pattern exact match): {item}{Fore.RESET}")
                return item

        # Try substring search for pattern-based candidates
        for candidate in primary_candidates:
            item = cache.find_item_by_search_term_fast(candidate)
            if item and not item.lower().endswith('.pub') and cluster_name not in item and '-crdb-node-prod' not in item:
                if debug:
                    print(f"{Fore.GREEN}✓ Found passphrase item (pattern substring match): {item}{Fore.RESET}")
                return item

    # Fallback to original logic if pattern matching fails
    if debug:
        print(f"{Fore.CYAN}Falling back to original search logic...{Fore.RESET}")

    base_name = cluster_name.replace('-crdb-node-prod-usw2-doordash', '').replace('-crdb-node-prod', '')
    base_name_with_hyphens = base_name.replace('_', '-')
    base_name_with_underscores = base_name.replace('-', '_')

    # Priority candidates (most likely to be correct)
    priority_candidates = [
        f"{base_name_with_hyphens} crdb prod",
        f"{base_name_with_underscores} crdb prod",
        f"{base_name_with_hyphens} crdb",
        f"{base_name_with_underscores} crdb"
    ]

    if debug:
        print(f"{Fore.CYAN}Searching for passphrase item for '{cluster_name}' using priority candidates:{Fore.RESET}")

    # Try priority candidates with exact match first
    for candidate in priority_candidates:
        if debug:
            print(f"  - {candidate}")

        # Try exact match first
        item = find_item_by_search_term_exact_match_only(cache, candidate)
        if item and not item.lower().endswith('.pub') and cluster_name not in item:
            if debug:
                print(f"{Fore.GREEN}✓ Found passphrase item (exact match): {item}{Fore.RESET}")
            return item

    # If exact matches fail, try substring search but with stricter filtering
    if debug:
        print(f"{Fore.CYAN}Trying substring search with strict filtering:{Fore.RESET}")

    for candidate in priority_candidates:
        if debug:
            print(f"  - {candidate} (substring)")

        item = cache.find_item_by_search_term_fast(candidate)
        if item and not item.lower().endswith('.pub') and cluster_name not in item and '-crdb-node-prod' not in item:
            if debug:
                print(f"{Fore.GREEN}✓ Found passphrase item (substring match): {item}{Fore.RESET}")
            return item
        elif item:
            if debug:
                reason = "contains cluster name" if cluster_name in item else "contains -crdb-node-prod" if '-crdb-node-prod' in item else "is .pub file"
                print(f"{Fore.YELLOW}⚠ Skipping item ({reason}): {item}{Fore.RESET}")

    # Extended fallback candidates
    extended_candidates = [
        f"{base_name_with_hyphens}-crdb-prod",
        f"{base_name_with_underscores}-crdb-prod",
        f"{base_name_with_hyphens}_crdb_prod",
        f"{base_name_with_underscores}_crdb_prod",
        base_name_with_hyphens,
        base_name_with_underscores,
        base_name
    ]

    if debug:
        print(f"{Fore.CYAN}Trying extended fallback candidates:{Fore.RESET}")

    for candidate in extended_candidates:
        if debug:
            print(f"  - {candidate}")

        item = cache.find_item_by_search_term_fast(candidate)
        if item and not item.lower().endswith('.pub') and cluster_name not in item and '-crdb-node-prod' not in item:
            if debug:
                print(f"{Fore.GREEN}✓ Found passphrase item (extended fallback): {item}{Fore.RESET}")
            return item

    if debug:
        print(f"{Fore.RED}✗ No passphrase item found for cluster: {cluster_name}{Fore.RESET}")

    return None

def download_private_key_ultra_fast(item_name, cluster_name, vault_id, item_details=None, debug=False):
    """Ultra-fast download using cached item details"""
    try:
        if not item_details:
            return None

        if 'files' in item_details and item_details['files']:
            file_info = item_details['files'][0]
            file_name = file_info.get('name', 'Unknown')

            output_filename = os.path.join(TEMP_KEY_DIR, cluster_name)

            result = subprocess.run(
                f'op read "op://{vault_id}/{item_name}/{file_name}" --out-file "{output_filename}"',
                shell=True,
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )

            if os.path.exists(output_filename):
                os.chmod(output_filename, 0o600)
                return output_filename

        return None
    except:
        return None

def setup_ssh_key_with_passphrase(cluster_name, key_file, passphrase, debug=False):
    """Setup SSH key - only proceeds if passphrase is provided"""
    if passphrase is None:
        if debug:
            print(f"{Fore.RED}✗ No passphrase for {cluster_name}, skipping SSH key addition{Fore.RESET}")
        return False

    ssh_dir = os.path.expanduser("~/.ssh")
    ssh_key_name = cluster_name.replace('-', '_')
    ssh_key_path = os.path.join(ssh_dir, ssh_key_name)

    try:
        # Fast copy
        shutil.copy2(key_file, ssh_key_path)
        os.chmod(ssh_key_path, 0o600)

        if debug:
            print(f"{Fore.CYAN}Adding {cluster_name} to ssh-agent with passphrase{Fore.RESET}")

        # Method 1: Try expect (most reliable for passphrases)
        expect_result = subprocess.run(
            ['which', 'expect'],
            capture_output=True,
            check=False
        )

        if expect_result.returncode == 0:
            # Create a robust expect script
            expect_script_content = f'''#!/usr/bin/expect -f
set timeout 10
log_user 0

spawn ssh-add "{ssh_key_path}"

expect {{
    -re "Enter passphrase.*:" {{
        send "{passphrase}\\r"
        expect {{
            "Identity added" {{
                exit 0
            }}
            "Bad passphrase" {{
                exit 1
            }}
            timeout {{
                exit 1
            }}
        }}
    }}
    "Identity added" {{
        exit 0
    }}
    timeout {{
        exit 1
    }}
    eof {{
        exit 0
    }}
}}
'''

            # Write expect script to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.exp', delete=False) as temp_script:
                temp_script.write(expect_script_content)
                temp_script_path = temp_script.name

            try:
                os.chmod(temp_script_path, 0o700)

                # Run expect script
                result = subprocess.run(
                    [temp_script_path],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False
                )

                if debug:
                    print(f"{Fore.CYAN}Expect result for {cluster_name}: {result.returncode}{Fore.RESET}")

                return result.returncode == 0

            finally:
                # Clean up temp script
                try:
                    os.unlink(temp_script_path)
                except:
                    pass

        # Method 2: Try SSH_ASKPASS as fallback
        if debug:
            print(f"{Fore.YELLOW}Trying SSH_ASKPASS method for {cluster_name}{Fore.RESET}")

        # Create a script that returns the passphrase
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as askpass_script:
            askpass_script.write(f'#!/bin/bash\necho "{passphrase}"\n')
            askpass_script_path = askpass_script.name

        try:
            os.chmod(askpass_script_path, 0o700)

            result = subprocess.run(
                f'ssh-add "{ssh_key_path}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                env={
                    **os.environ,
                    'SSH_ASKPASS': askpass_script_path,
                    'DISPLAY': ':0',
                    'SSH_ASKPASS_REQUIRE': 'force'
                }
            )

            if debug:
                print(f"{Fore.CYAN}SSH_ASKPASS result for {cluster_name}: {result.returncode}{Fore.RESET}")

            return result.returncode == 0

        finally:
            try:
                os.unlink(askpass_script_path)
            except:
                pass

    except Exception as e:
        if debug:
            print(f"{Fore.RED}Error processing {cluster_name}: {e}{Fore.RESET}")
        return False

    # If all methods fail
    if debug:
        print(f"{Fore.RED}All methods failed for {cluster_name}{Fore.RESET}")
    return False

def check_ssh_key_loaded(cluster_name, debug=False):
    """Check if SSH key is already loaded in ssh-agent"""
    ssh_key_name = cluster_name.replace('-', '_')

    try:
        result = subprocess.run(
            'ssh-add -l',
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )

        if result.returncode == 0 and ssh_key_name in result.stdout:
            if debug:
                print(f"{Fore.GREEN}✓ {cluster_name} already loaded in ssh-agent{Fore.RESET}")
            return True

    except:
        pass

    return False

def process_clusters_sequential(clusters, cache, vault_id, debug=False):
    """Process clusters sequentially - now searches for passphrases in separate items"""

    # Step 0: Filter out already loaded keys
    clusters_to_process = []
    already_loaded = 0

    for cluster_name in clusters:
        if check_ssh_key_loaded(cluster_name, debug):
            already_loaded += 1
        else:
            clusters_to_process.append(cluster_name)

    if debug and already_loaded > 0:
        print(f"{Fore.GREEN}{already_loaded} keys already loaded, processing {len(clusters_to_process)} remaining{Fore.RESET}")

    if not clusters_to_process:
        if debug:
            print(f"{Fore.GREEN}All keys already loaded!{Fore.RESET}")
        return {cluster: True for cluster in clusters}

    # Step 1: Collect all item names we need (both key files and passphrase items)
    key_item_names_needed = set()
    passphrase_item_names_needed = set()
    cluster_to_key_items = {}
    cluster_to_passphrase_items = {}

    for cluster_name in clusters_to_process:
        # Find key file item
        key_item_name = find_item_by_cluster_name(cache, cluster_name, debug)
        if key_item_name:
            cluster_to_key_items[cluster_name] = key_item_name
            key_item_names_needed.add(key_item_name)
        else:
            cluster_to_key_items[cluster_name] = None

        # Find passphrase item (separate from key item) - use improved search
        passphrase_item_name = find_passphrase_item_for_cluster_improved(cache, cluster_name, debug)
        if passphrase_item_name:
            cluster_to_passphrase_items[cluster_name] = passphrase_item_name
            passphrase_item_names_needed.add(passphrase_item_name)
        else:
            cluster_to_passphrase_items[cluster_name] = None

    # Step 2: Batch fetch all item details (this can be parallel)
    all_item_names = list(key_item_names_needed) + list(passphrase_item_names_needed)

    if debug:
        print(f"{Fore.CYAN}Batch fetching {len(all_item_names)} item details ({len(key_item_names_needed)} key items, {len(passphrase_item_names_needed)} passphrase items)...{Fore.RESET}")

    item_details = cache.batch_get_item_details(all_item_names, debug)

    # Step 3: Download all keys and get passphrases in parallel
    cluster_data = {}

    def download_cluster_key_and_passphrase(cluster_name):
        try:
            # Get key file
            key_item_name = cluster_to_key_items[cluster_name]
            key_file = None
            if key_item_name:
                key_file = download_private_key_ultra_fast(
                    key_item_name,
                    cluster_name,
                    vault_id,
                    item_details.get(key_item_name),
                    debug
                )

            # Get passphrase from separate item
            passphrase_item_name = cluster_to_passphrase_items[cluster_name]
            passphrase = None
            if passphrase_item_name:
                passphrase = get_ssh_key_passphrase_from_item(passphrase_item_name, vault_id, debug)

            return cluster_name, key_file, passphrase

        except Exception as e:
            if debug:
                print(f"{Fore.RED}Error processing {cluster_name}: {e}{Fore.RESET}")
            return cluster_name, None, None

    # Parallel downloads and passphrase retrieval
    if debug:
        print(f"{Fore.CYAN}Downloading {len(clusters_to_process)} keys and getting passphrases in parallel...{Fore.RESET}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        download_futures = {executor.submit(download_cluster_key_and_passphrase, cluster): cluster for cluster in clusters_to_process}

        for future in concurrent.futures.as_completed(download_futures):
            cluster_name, key_file, passphrase = future.result()
            cluster_data[cluster_name] = (key_file, passphrase)

    # Step 4: Sequential ssh-add to avoid conflicts, but only if passphrase exists
    if debug:
        print(f"{Fore.CYAN}Adding keys to ssh-agent sequentially (only with valid passphrases)...{Fore.RESET}")

    results = {}

    # Mark already loaded keys as successful
    for cluster_name in clusters:
        if cluster_name not in clusters_to_process:
            results[cluster_name] = True

    # Process the remaining keys
    for cluster_name in clusters_to_process:
        key_file, passphrase = cluster_data.get(cluster_name, (None, None))

        if key_file and passphrase:
            # Both key file and passphrase found - proceed
            success = setup_ssh_key_with_passphrase(cluster_name, key_file, passphrase, debug)
            results[cluster_name] = success

            if not debug:
                status = f"{Fore.GREEN}✓" if success else f"{Fore.RED}✗"
                print(f"{status} {cluster_name}{Fore.RESET}")

        elif key_file and passphrase is None:
            # Key file found but no passphrase - report specific failure
            results[cluster_name] = False
            if debug:
                print(f"{Fore.RED}✗ {cluster_name} - key found but no passphrase in 1Password{Fore.RESET}")
            else:
                print(f"{Fore.RED}✗ {cluster_name} (no passphrase){Fore.RESET}")

        else:
            # No key file found
            results[cluster_name] = False
            if debug:
                print(f"{Fore.RED}✗ {cluster_name} - no key file found{Fore.RESET}")
            else:
                print(f"{Fore.RED}✗ {cluster_name} (not found){Fore.RESET}")

    return results

def process_all_clusters_ultra_fast(account, debug=False):
    """Ultra-fast processing with hybrid parallel/sequential approach"""
    vault_id = 'lfnuhv7jc72reknrdqlkup2ubm'
    cache = OnePasswordCache(account, vault_id)

    print(f"{Fore.YELLOW}Finding cluster items...{Fore.RESET}")
    clusters = find_all_cluster_items_ultra_fast(cache, debug)

    if not clusters:
        print(f"{Fore.RED}No clusters found{Fore.RESET}")
        return

    print(f"{Fore.GREEN}Found {len(clusters)} clusters. Processing...{Fore.RESET}")

    # Process in smaller batches to manage resources
    batch_size = 25
    total_successful = 0
    total_failed = 0

    for i in range(0, len(clusters), batch_size):
        batch = clusters[i:i + batch_size]
        if debug:
            print(f"{Fore.CYAN}Processing batch {i//batch_size + 1}: {len(batch)} clusters{Fore.RESET}")

        results = process_clusters_sequential(batch, cache, vault_id, debug)

        successful = sum(1 for success in results.values() if success)
        failed = len(batch) - successful

        total_successful += successful
        total_failed += failed

    # Return the totals instead of printing them here
    return total_successful, total_failed

def main():
    parser = argparse.ArgumentParser(description="Ultra-fast SSH key retrieval from 1Password")
    parser.add_argument('-c', '--cluster', help='Single cluster name')
    parser.add_argument('-a', '--account', default='doordash.1password.com', help='1Password account')
    parser.add_argument('--add-all', action='store_true', help='Add all matching keys')
    parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')

    args = parser.parse_args()

    if args.add_all and args.cluster:
        print(f"{Fore.RED}Error: Cannot specify both --cluster and --add-all{Fore.RESET}")
        return

    if not args.add_all and not args.cluster:
        print(f"{Fore.RED}Error: Must specify either --cluster or --add-all{Fore.RESET}")
        return

    # Setup clean temp directory
    setup_temp_directory(args.debug)

    # Store results for final summary
    total_successful = 0
    total_failed = 0

    try:
        if args.add_all:
            total_successful, total_failed = process_all_clusters_ultra_fast(args.account, args.debug)
        else:
            vault_id = 'lfnuhv7jc72reknrdqlkup2ubm'
            cache = OnePasswordCache(args.account, vault_id)
            results = process_clusters_sequential([args.cluster], cache, vault_id, args.debug)
            success = results.get(args.cluster, False)

            if success:
                print(f"{Fore.GREEN}✓ Successfully processed {args.cluster}{Fore.RESET}")
                total_successful = 1
                total_failed = 0
            else:
                print(f"{Fore.RED}✗ Failed to process {args.cluster}{Fore.RESET}")
                total_successful = 0
                total_failed = 1
    finally:
        cleanup_temp_keys(args.debug)

        # Print final summary as the very last thing
        if args.add_all or args.cluster:
            print(f"\n{Fore.GREEN}Success: {total_successful}{Fore.RESET} | {Fore.RED}Failed: {total_failed}{Fore.RESET}")
            print(f"{Fore.YELLOW}Note: Failed items include clusters without passphrases in 1Password{Fore.RESET}")

def get_ssh_key_passphrase_from_item(passphrase_item_name, vault_id, debug=False):
    """Get SSH key passphrase from a specific 1Password item"""
    # Safety check: never try to get passphrase from .pub items
    if passphrase_item_name.lower().endswith('.pub'):
        if debug:
            print(f"{Fore.YELLOW}⚠ Skipping passphrase retrieval from .pub item: {passphrase_item_name}{Fore.RESET}")
        return None

    try:
        result = subprocess.run(
            f'op item get "{passphrase_item_name}" --vault {vault_id} --fields label=ssh-key-passphrase --reveal',
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )

        passphrase = result.stdout.strip()

        if passphrase:
            if debug:
                print(f"{Fore.GREEN}✓ Found passphrase in {passphrase_item_name}{Fore.RESET}")
            return passphrase
        else:
            if debug:
                print(f"{Fore.YELLOW}⚠ Empty passphrase in {passphrase_item_name}{Fore.RESET}")
            return None

    except subprocess.CalledProcessError as e:
        if debug:
            print(f"{Fore.RED}✗ No passphrase field found in {passphrase_item_name}: {e}{Fore.RESET}")
        return None
    except Exception as e:
        if debug:
            print(f"{Fore.RED}✗ Error retrieving passphrase from {passphrase_item_name}: {e}{Fore.RESET}")
        return None

if __name__ == "__main__":
    main()