import urllib.request
import json

def get(url):
    print(f"Fetching {url}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print(f"Success! Got {len(data)} items.")
            if data:
                print(json.dumps(data[0], indent=2))
    except Exception as e:
        print(f"Error: {e}")

# Try exact match
get("http://layers.openembedded.org/layerindex/api/recipes/?filter=name:tailscale")

# Try without filter but probably large, so maybe not wise.
# But let's try a very specific known recipe ID if possible? No.

# Try different filter syntax if possible?
get("http://layers.openembedded.org/layerindex/api/recipes/?filter=pn:tailscale")

# Try branches endpoint to confirm my suspicion about it being working
get("http://layers.openembedded.org/layerindex/api/layerBranches/?filter=layer:46") 
