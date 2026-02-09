#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from packaging.version import parse as parse_version
sys.path.insert(0, str(Path(__file__).resolve().parent))
from yocto_layer_index import LayerIndex, DEFAULT_BRANCH
try:
    from yocto_utils import get_yocto_branch, UI
except ImportError:
    def get_yocto_branch(root): return DEFAULT_BRANCH
    class UI:
        BOLD = CYAN = GREEN = RED = YELLOW = DIM = NC = ''
        @classmethod
        def print_header(cls, text): print(text)
        @classmethod
        def print_item(cls, l, v): print(f"{l}: {v}")

def main():
    root = Path(__file__).resolve().parent.parent
    default_branch = get_yocto_branch(root)
    
    parser = argparse.ArgumentParser(description="Search for recipes in the OpenEmbedded Layer Index")
    parser.add_argument("term", help="Search term (recipe name)")
    parser.add_argument("--branch", default=default_branch, help=f"Yocto branch to search (default: {default_branch})")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of results")
    args = parser.parse_args()

    UI.print_header("Yocto Recipe Search")
    UI.print_item("Search Term", args.term)
    UI.print_item("Branch", args.branch)

    index = LayerIndex(branch=args.branch)
    # Ensure branch ID is valid
    if not index.get_branch_id():
        UI.print_error(f"Branch '{args.branch}' not found in Layer Index.", fatal=True)

    recipes = index.search_recipes(args.term)
    
    if not recipes:
        UI.print_warning(f"No recipes found matching '{args.term}' on the Layer Index.")
        sys.exit(0)

    # Filter and resolve details
    results = []
    UI.print_item("Matches", str(len(recipes)))
    
    count = 0
    for r in recipes:
        info = index.get_recipe_layer_info(r)
        if info:
            results.append(info)
    
    if not results:
        UI.print_error(f"No recipes found for branch '{args.branch}' matching '{args.term}'.")
        print(f"  Note: {len(recipes)} recipes matched the name, but none were compatible with branch '{args.branch}'.")
        sys.exit(0)

    # Sort by version (newest first)
    results.sort(key=lambda x: parse_version(x['version']), reverse=True)
    
    # Apply limit after sorting
    results = results[:args.limit]

    # Display results
    print(f"\n  {UI.BOLD}{'Recipe':<30} {'Version':<20} {'Layer':<25} {'Summary'}{UI.NC}")
    print("  " + "-" * 100)
    for res in results:
        summary = res['summary'][:40] + "..." if len(res['summary']) > 40 else res['summary']
        print(f"  {UI.GREEN}{res['recipe_name']:<30}{UI.NC} {res['version']:<20} {UI.CYAN}{res['layer_name']:<25}{UI.NC} {summary}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
