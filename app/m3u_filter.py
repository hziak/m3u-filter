from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
import aiohttp
import asyncio
from cachetools import TTLCache
from typing import List, Tuple
import hashlib

app = FastAPI(title="M3U Filter Service")

# Cache: key -> filtered m3u content
# Size can be adjusted based on expected usage
cache = TTLCache(maxsize=1000, ttl=60 * 60)  # 60 minutes TTL

def generate_cache_key(url: str, keywords: Tuple[str, ...]) -> str:
    key_string = url + "|" + ",".join(sorted(keywords))
    return hashlib.sha256(key_string.encode('utf-8')).hexdigest()

async def fetch_m3u(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with session.get(url) as response:
            if response.status != 200:
                raise HTTPException(status_code=400, detail=f"Failed to fetch M3U file. Status code: {response.status}")
            return await response.text()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching M3U file: {str(e)}")

def filter_m3u(content: str, keywords: List[str]) -> str:
    lines = content.splitlines()
    filtered_lines = []
    include = False
    for line in lines:
        if line.startswith("#EXTINF"):
            # Check if any keyword is in the line (case-insensitive)
            if any(keyword in line for keyword in keywords):
                include = True
                filtered_lines.append(line.encode('utf-8'))
            else:
                include = False
        elif line.startswith("#") or not line.strip():
            if include:
                filtered_lines.append(line.encode('utf-8'))
        else:
            if include:
                filtered_lines.append(line.encode('utf-8'))
    return "\n".join(filtered_lines)

@app.get("/filter_m3u", response_class=Response, summary="Filter M3U by keywords")
async def filter_m3u_endpoint(
    url: str = Query(..., description="URL of the M3U file to filter"),
    keywords: List[str] = Query(..., description="Keywords to filter the streams")
):
    if not keywords:
        raise HTTPException(status_code=400, detail="At least one keyword must be provided.")

    cache_key = generate_cache_key(url, tuple(keywords))
    
    if cache_key in cache:
        filtered_m3u = cache[cache_key]
    else:
        async with aiohttp.ClientSession() as session:
            m3u_content = await fetch_m3u(session, url)
        
        # Perform filtering
        loop = asyncio.get_event_loop()
        filtered_m3u = await loop.run_in_executor(None, filter_m3u, m3u_content, keywords)
        
        # Cache the result
        cache[cache_key] = filtered_m3u

    return Response(content=filtered_m3u, media_type="application/vnd.apple.mpegurl")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("m3u_filter:app", host="0.0.0.0", port=8000, reload=True)
