import struct
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
import aiohttp
import asyncio
from cachetools import TTLCache
from typing import List, Tuple
import hashlib
import chardet

app = FastAPI(title="M3U Filter Service")

# Cache: key -> filtered m3u content
# Size can be adjusted based on expected usage
cache = TTLCache(maxsize=1000, ttl=60 * 600)  # 60 minutes TTL


def generate_cache_key(url: str, keywords: Tuple[str, ...]) -> str:
    key_string = url + "|" + ",".join(sorted(keywords))
    return hashlib.sha256(key_string.encode('utf-8')).hexdigest()


def rawbytes(s):
    """Convert a string to raw bytes without encoding"""
    outlist = []
    for cp in s:
        num = ord(cp)
        if num < 255:
            outlist.append(struct.pack('B', num))
        elif num < 65535:
            outlist.append(struct.pack('>H', num))
        else:
            b = (num & 0xFF0000) >> 16
            H = num & 0xFFFF
            outlist.append(struct.pack('>bH', b, H))
    return b''.join(outlist)


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
    encoding = chardet.detect(rawbytes(keywords[0]))
    print(encoding)
    # lines = content.decode(encoding).encode('utf-8').splitlines()
    # lines = content.splitlines()
    filtered_lines = []
    include = False
    for line in lines:
        # try:
        #     line = line_wrong_encoding.encode('Windows-1252').decode('utf-8')
        # except:
        #     line = line_wrong_encoding
        if line.startswith("#EXTINF"):
        #     # Check if any keyword is in the line (case-insensitive)
        #     print(line)
            if any(keyword.encode(encoding['encoding']).decode('utf-8') in line for keyword in keywords):
                print("Keyword found in line")
                include = True
                try:
                    filtered_lines.append(line.encode('Windows-1252').decode('utf-8'))
                except:
                    print("Line excluded: "+ line)
                    include = False
            else:
                include = False
        elif line.startswith("#") or not line.strip():
            if include:
                filtered_lines.append(line)
        else:
            if include:
                filtered_lines.append(line)
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
