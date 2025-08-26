#!/usr/bin/env python3

import re
import argparse
from colorama import Fore, init

# Initialize colorama
init()

def load_file_lines(filepath):
    """Load lines from a file, stripping whitespace and ignoring comments/empty lines"""
    try:
        with open(filepath, 'r') as f:
            lines = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    lines.append(line)
            return lines
    except FileNotFoundError:
        print(f"{Fore.RED}Error: File {filepath} not found{Fore.RESET}")
        return []

def normalize_cluster_name(cluster_name):
    """Convert cluster name to expected SSH key format"""
    # Remove any suffix that might be added
    normalized = cluster_name

    # Replace hyphens with underscores
    normalized = normalized.replace('-', '_')

    return normalized

def reverse_normalize(ssh_key_name):
    """Convert SSH key name back to cluster format for comparison"""
    # Replace underscores with hyphens
    return ssh_key_name.replace('_', '-')

def find_potential_matches(missing_cluster, ssh_keys):
    """Find potential matches for a missing cluster using fuzzy matching"""
    cluster_parts = missing_cluster.replace('-', ' ').split()
    potential_matches = []

    for ssh_key in ssh_keys:
        ssh_parts = ssh_key.replace('_', ' ').split()

        # Check for partial matches
        common_parts = set(cluster_parts) & set(ssh_parts)
        if len(common_parts) >= 2:  # At least 2 words in common
            match_ratio = len(common_parts) / max(len(cluster_parts), len(ssh_parts))
            potential_matches.append((ssh_key, match_ratio, common_parts))

    # Sort by match ratio descending
    potential_matches.sort(key=lambda x: x[1], reverse=True)
    return potential_matches[:3]  # Return top 3 matches

def analyze_naming_patterns(clusters, ssh_keys):
    """Analyze naming patterns and differences"""
    patterns = {
        'exact_match': [],
        'normalized_match': [],
        'missing_completely': [],
        'extra_ssh_keys': [],
        'potential_matches': {}
    }

    ssh_keys_set = set(ssh_keys)
    clusters_set = set(clusters)

    # Convert SSH keys back to cluster format for comparison
    ssh_as_clusters = {reverse_normalize(key): key for key in ssh_keys}

    print(f"{Fore.CYAN}=== ANALYSIS REPORT ==={Fore.RESET}")
    print(f"Total clusters: {len(clusters)}")
    print(f"Total SSH keys: {len(ssh_keys)}")
    print()

    # Check each cluster
    for cluster in clusters:
        normalized = normalize_cluster_name(cluster)

        if normalized in ssh_keys_set:
            patterns['exact_match'].append((cluster, normalized))
        elif cluster in ssh_as_clusters:
            patterns['normalized_match'].append((cluster, ssh_as_clusters[cluster]))
        else:
            patterns['missing_completely'].append(cluster)
            # Find potential matches
            potential = find_potential_matches(cluster, ssh_keys)
            if potential:
                patterns['potential_matches'][cluster] = potential

    # Find SSH keys that don't match any cluster
    cluster_normalized = {normalize_cluster_name(c) for c in clusters}
    cluster_as_ssh = {reverse_normalize(c) for c in clusters}

    for ssh_key in ssh_keys:
        if ssh_key not in cluster_normalized and reverse_normalize(ssh_key) not in clusters_set:
            patterns['extra_ssh_keys'].append(ssh_key)

    return patterns

def print_analysis_results(patterns):
    """Print detailed analysis results"""

    # Exact matches
    print(f"{Fore.GREEN}=== EXACT MATCHES ({len(patterns['exact_match'])}) ==={Fore.RESET}")
    for cluster, ssh_key in patterns['exact_match'][:5]:  # Show first 5
        print(f"  ✓ {cluster} → {ssh_key}")
    if len(patterns['exact_match']) > 5:
        print(f"  ... and {len(patterns['exact_match']) - 5} more")
    print()

    # Normalized matches
    if patterns['normalized_match']:
        print(f"{Fore.YELLOW}=== NORMALIZED MATCHES ({len(patterns['normalized_match'])}) ==={Fore.RESET}")
        for cluster, ssh_key in patterns['normalized_match']:
            print(f"  ~ {cluster} → {ssh_key}")
        print()

    # Missing completely
    print(f"{Fore.RED}=== MISSING SSH KEYS ({len(patterns['missing_completely'])}) ==={Fore.RESET}")
    for cluster in patterns['missing_completely']:
        print(f"  ✗ {cluster}")

        # Show potential matches
        if cluster in patterns['potential_matches']:
            potential = patterns['potential_matches'][cluster]
            print(f"    {Fore.CYAN}Potential matches:{Fore.RESET}")
            for ssh_key, ratio, common_parts in potential:
                print(f"      - {ssh_key} (similarity: {ratio:.2f}, common: {', '.join(common_parts)})")
    print()

    # Extra SSH keys
    if patterns['extra_ssh_keys']:
        print(f"{Fore.MAGENTA}=== EXTRA SSH KEYS ({len(patterns['extra_ssh_keys'])}) ==={Fore.RESET}")
        for ssh_key in patterns['extra_ssh_keys']:
            print(f"  + {ssh_key}")
        print()

def generate_missing_keys_script(missing_clusters, output_file=None):
    """Generate a script to create missing SSH keys"""
    script_content = f'''#!/bin/bash
# Script to add missing SSH keys
# Generated automatically

echo "Adding {len(missing_clusters)} missing SSH keys..."

'''

    for cluster in missing_clusters:
        normalized = normalize_cluster_name(cluster)
        script_content += f'echo "Processing {cluster}..."\n'
        script_content += f'python3 add_keys.py -c {cluster}-crdb-node-prod-usw2-doordash\n'
        script_content += f'if [ $? -eq 0 ]; then\n'
        script_content += f'    echo "✓ Successfully added {cluster}"\n'
        script_content += f'else\n'
        script_content += f'    echo "✗ Failed to add {cluster}"\n'
        script_content += f'fi\n'
        script_content += f'echo ""\n\n'

    script_content += 'echo "Finished processing missing keys."\n'

    if output_file:
        with open(output_file, 'w') as f:
            f.write(script_content)
        print(f"{Fore.GREEN}Generated script: {output_file}{Fore.RESET}")
        print(f"To run: chmod +x {output_file} && ./{output_file}")
    else:
        print(f"{Fore.CYAN}=== GENERATED SCRIPT ==={Fore.RESET}")
        print(script_content)

def main():
    parser = argparse.ArgumentParser(description="Analyze missing SSH keys and naming patterns")
    parser.add_argument('-c', '--clusters-file', default='/Users/shamer/key_count.txt',
                       help='File containing cluster names (default: /Users/shamer/key_count.txt)')
    parser.add_argument('-s', '--ssh-keys-file', default='/Users/shamer/add_keys_key_list.txt',
                       help='File containing SSH key names (default: /Users/shamer/add_keys_key_list.txt)')
    parser.add_argument('-o', '--output-script',
                       help='Generate a script file to add missing keys')
    parser.add_argument('--summary-only', action='store_true',
                       help='Show only summary statistics')
    parser.add_argument('--missing-only', action='store_true',
                       help='Show only missing clusters')

    args = parser.parse_args()

    # Load data
    clusters = load_file_lines(args.clusters_file)
    ssh_keys = load_file_lines(args.ssh_keys_file)

    if not clusters or not ssh_keys:
        return

    # Analyze patterns
    patterns = analyze_naming_patterns(clusters, ssh_keys)

    if args.summary_only:
        print(f"{Fore.CYAN}=== SUMMARY ==={Fore.RESET}")
        print(f"Total clusters: {len(clusters)}")
        print(f"Total SSH keys: {len(ssh_keys)}")
        print(f"Exact matches: {len(patterns['exact_match'])}")
        print(f"Normalized matches: {len(patterns['normalized_match'])}")
        print(f"Missing SSH keys: {len(patterns['missing_completely'])}")
        print(f"Extra SSH keys: {len(patterns['extra_ssh_keys'])}")
        print(f"Coverage: {(len(patterns['exact_match']) + len(patterns['normalized_match'])) / len(clusters) * 100:.1f}%")

    elif args.missing_only:
        print(f"{Fore.RED}=== MISSING SSH KEYS ({len(patterns['missing_completely'])}) ==={Fore.RESET}")
        for cluster in patterns['missing_completely']:
            print(cluster)

    else:
        print_analysis_results(patterns)

    # Generate script if requested
    if args.output_script:
        generate_missing_keys_script(patterns['missing_completely'], args.output_script)

    # Final summary
    print(f"\n{Fore.CYAN}=== SUMMARY ==={Fore.RESET}")
    total_coverage = len(patterns['exact_match']) + len(patterns['normalized_match'])
    coverage_percent = total_coverage / len(clusters) * 100
    print(f"Coverage: {total_coverage}/{len(clusters)} ({coverage_percent:.1f}%)")
    print(f"Missing: {len(patterns['missing_completely'])} clusters need SSH keys")
    print(f"Extra: {len(patterns['extra_ssh_keys'])} SSH keys don't match clusters")

if __name__ == "__main__":
    main()