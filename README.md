# Skanderbeg Save Data Gateway with Persistent Caching

Caching wrapper for Skanderbegs API

## Endpoints

**GET /savefiles**
- List all save files
- No auth required
- Returns: `[{id: string, user_id: string, metadata: object, created_at: string, updated_at: string, size: int}, ...]`

**POST /savefiles**
- Upload a compressed save file
- Admin only
- Returns: `{id: string, user_id: string, metadata: object, created_at: string, size: int}`

**GET /savefiles/{savefile_id}**
- Download a save file
- No auth required
- Returns: `{id: string, user_id: string, metadata: object, created_at: string, updated_at: string, compressed_data: string (hex), size: int}`

**PUT /savefiles/{savefile_id}**
- Update file data and/or metadata
- Admin only
- Returns: `{id: string, user_id: string, metadata: object, updated_at: string, size: int}`

**DELETE /savefiles/{savefile_id}**
- Delete a save file
- Admin only
- Returns: `{success: bool, id: string}`