from fastapi import FastAPI, HTTPException, Query
import os
import hashlib
import json
import logging
from typing import Optional
from datetime import datetime
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Skanderbeg API Gateway with Caching")

# Configuration
BASE_API_URL = os.getenv("BASE_API_URL", "http://skanderbeg.pm/api.php")
CACHE_DIR = Path(os.getenv("CACHE_DIR", "./cache"))

# Ensure cache directory exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)

logger.info(f"Cache directory: {CACHE_DIR}")
logger.info(f"Base API URL: {BASE_API_URL}")


def get_cache_path(query_params: str) -> Path:
    """Generate cache file path from query parameters."""
    hash_key = hashlib.md5(query_params.encode()).hexdigest()
    return CACHE_DIR / f"{hash_key}.json"


def get_from_cache(query_params: str) -> Optional[dict]:
    """Retrieve data from persistent cache."""
    cache_path = get_cache_path(query_params)
    if cache_path.exists():
        try:
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)
                logger.info(f"Cache hit for: {query_params}")
                return cached_data
        except Exception as e:
            logger.error(f"Error reading cache: {e}")
            return None
    return None


def save_to_cache(query_params: str, data: dict) -> None:
    """Save data to persistent cache."""
    cache_path = get_cache_path(query_params)
    try:
        with open(cache_path, 'w') as f:
            json.dump(data, f)
            logger.info(f"Cached data for: {query_params}")
    except Exception as e:
        logger.error(f"Error writing cache: {e}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "cache_dir": str(CACHE_DIR),
        "cache_size_mb": sum(f.stat().st_size for f in CACHE_DIR.glob('**/*') if f.is_file()) / (1024 * 1024)
    }


@app.get("/api/getSaveDataDump")
async def get_save_data_dump(save: str = Query(..., description="Save ID"), type: str = Query("countriesData", description="Data type")):
    """
    Proxy endpoint for Skanderbeg save data with persistent caching.
    
    Parameters:
    - save: Save ID to fetch
    - type: Data type (default: countriesData)
    
    Returns:
    - Cached or fresh save data
    """
    try:
        # Check persistent cache first
        query_key = f"save={save}&type={type}"
        cached_result = get_from_cache(query_key)
        if cached_result:
            logger.info(f"Returning cached data for save={save}")
            return cached_result.get("data")

        # Call external API
        logger.info(f"Cache miss, fetching from Skanderbeg API: save={save}")
        response = requests.get(
            BASE_API_URL,
            params={
                "scope": "getSaveDataDump",
                "save": save,
                "type": type
            },
            timeout=30
        )
        response.raise_for_status()

        api_data = response.json()

        # Save to persistent cache
        cache_entry = {
            "data": api_data,
            "timestamp": datetime.utcnow().isoformat(),
            "save": save,
            "type": type
        }
        save_to_cache(query_key, cache_entry)

        return api_data

    except requests.exceptions.RequestException as e:
        logger.error(f"Skanderbeg API error: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"External API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )





if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
