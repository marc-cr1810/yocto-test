#!/usr/bin/env python3
import json
import urllib.request
import urllib.parse
from typing import List, Dict, Optional, Any
import sys

LAYER_INDEX_API_URL = "http://layers.openembedded.org/layerindex/api"
DEFAULT_BRANCH = "master"

class LayerIndex:
    def __init__(self, branch: str = DEFAULT_BRANCH):
        self.branch = branch
        self._branch_id = None
        self._layerbranch_cache = {}  # id -> lb_info
        self._layer_cache = {}        # id -> layer_info
        self._prefetched_branches = False
        
    def _make_request(self, endpoint: str, params: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """Helper to make GET requests to the Layer Index API."""
        url = f"{LAYER_INDEX_API_URL}/{endpoint}/"
        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'yocto-search/1.0'})
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    return json.loads(response.read().decode())
                return []
        except Exception as e:
            # Silently fail or log for now, as CLI tools handle empty results
            # print(f"DEBUG: Error querying {url}: {e}", file=sys.stderr)
            return []

    def get_branch_id(self) -> Optional[int]:
        if self._branch_id:
            return self._branch_id
        
        results = self._make_request("branches", {"filter": f"name:{self.branch}"})
        if results:
            self._branch_id = results[0]['id']
            return self._branch_id
        return None

    def prefetch_layerbranches(self):
        """Fetch all layerbranches for the current branch to speed up filtering."""
        if self._prefetched_branches:
            return
            
        branch_id = self.get_branch_id()
        if not branch_id:
            return
            
        # This might return a few hundred items, which is fine
        results = self._make_request("layerBranches", {"filter": f"branch:{branch_id}"})
        for lb in results:
            self._layerbranch_cache[lb['id']] = lb
        self._prefetched_branches = True

    def search_recipes(self, keyword: str) -> List[Dict[str, Any]]:
        """
        Search for recipes by name (exact or substring).
        Returns a list of recipes. Note: DOES NOT filter by branch yet.
        """
        return self._make_request("recipes", {"filter": f"pn__icontains:{keyword}"})

    def get_layerbranch(self, layerbranch_id: int) -> Optional[Dict[str, Any]]:
        if layerbranch_id in self._layerbranch_cache:
            return self._layerbranch_cache[layerbranch_id]
            
        results = self._make_request("layerBranches", {"filter": f"id:{layerbranch_id}"})
        if results:
            self._layerbranch_cache[layerbranch_id] = results[0]
            return results[0]
        return None

    def get_layer_item(self, layer_id: int) -> Optional[Dict[str, Any]]:
        if layer_id in self._layer_cache:
            return self._layer_cache[layer_id]
            
        results = self._make_request("layerItems", {"filter": f"id:{layer_id}"})
        if results:
            self._layer_cache[layer_id] = results[0]
            return results[0]
        return None

    def get_layer_dependencies(self, layer_id: int) -> List[Dict[str, Any]]:
        """
        Get dependencies for a layer in the current branch.
        Returns a list of dependency layer items.
        """
        branch_id = self.get_branch_id()
        if not branch_id:
            return []
            
        # 1. Find correct LayerBranch
        # We need to filter by both layer and branch, but since we can't reliably do multiple filters,
        # we fetch by layer and filter in Python.
        # Optimziation: Fetch deps by layerbranch ID directly if known? 
        # But we start with layer_id usually.
        
        # Get all branches for this layer
        layerbranches = self._make_request("layerBranches", {"filter": f"layer:{layer_id}"})
        target_lb = None
        for lb in layerbranches:
            if lb['branch'] == branch_id:
                target_lb = lb
                break
        
        if not target_lb:
            return []
            
        # 2. Get dependencies
        deps = self._make_request("layerDependencies", {"filter": f"layerbranch:{target_lb['id']}"})
        
        # 3. Resolve to layer items
        dep_layers = []
        for d in deps:
            dep_layer_id = d['dependency']
            # We could optimize this by fetching items in batch or caching, 
            # but usually deps are few (<5).
            l = self.get_layer_item(dep_layer_id)
            if l:
                dep_layers.append(l)
                
        return dep_layers

    # Previous duplicate get_layerbranch removed if it existed, but here we replace up to get_recipe_layer_info
    
    def get_recipe_layer_info(self, recipe: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Given a recipe dict, resolve the layer it belongs to, checking against the target branch.
        Returns a dict with combined info if valid, else None.
        """
        # Prefetch if not already done to ensure fast lookups
        if not self._prefetched_branches and not self._layerbranch_cache:
             self.prefetch_layerbranches()

        lb_id = recipe.get('layerbranch')
        if not lb_id:
            return None
            
        lb = self.get_layerbranch(lb_id)
        if not lb:
            return None
            
        # Verify branch matches the target branch
        # We need the branch ID to compare
        target_branch_id = self.get_branch_id()
        if target_branch_id and lb['branch'] != target_branch_id:
            return None
                
        layer_id = lb['layer']
        layer = self.get_layer_item(layer_id)
        if not layer:
            return None
            
        return {
            "layer_name": layer['name'],
            "recipe_name": recipe['pn'],
            "version": recipe['pv'],
            "summary": recipe['summary'],
            "layer_vcs_url": layer['vcs_url'],
            "layer_web_url": layer.get('vcs_web_url', ''),
            "vcs_subdir": lb.get('vcs_subdir', ''),
            "actual_branch": lb.get('actual_branch') or self.branch,
            "layer_index_url": layer.get('vcs_web_url', '') # redundant but for compatibility
        }

    def search_layers(self, keyword: str) -> List[Dict[str, Any]]:
        return self._make_request("layerItems", {"filter": f"name__icontains:{keyword}"})

    def search_machines(self, keyword: str) -> List[Dict[str, Any]]:
        """
        Search for machines by name.
        """
        # Search machines triggers the need for filtering, so prefetch branches
        self.prefetch_layerbranches()
        return self._make_request("machines", {"filter": f"name__icontains:{keyword}"})

    def get_machine_layer_info(self, machine: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Resolve layer info for a machine.
        """
        lb_id = machine.get('layerbranch')
        if not lb_id:
            return None
            
        # This will now hit cache
        lb = self.get_layerbranch(lb_id)
        if not lb:
            return None
            
        # Verify branch matches the target branch
        target_branch_id = self.get_branch_id()
        if target_branch_id and lb['branch'] != target_branch_id:
            return None
            
        layer_id = lb['layer']
        layer = self.get_layer_item(layer_id)
        if not layer:
            return None
            
        return {
            "layer_name": layer['name'],
            "machine_name": machine['name'],
            "description": machine['description'],
            "layer_vcs_url": layer['vcs_url'],
            "layer_web_url": layer.get('vcs_web_url', ''),
            "vcs_subdir": lb.get('vcs_subdir', ''),
            "actual_branch": lb.get('actual_branch') or self.branch
        }

