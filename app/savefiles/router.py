import logging
import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .database import get_db, SaveFile
from .auth import verify_jwt, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/savefiles", tags=["savefiles"])


@router.get("")
async def list_savefiles(
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """
    List all save files with metadata.
    
    - Anyone can list (no auth required)
    - Returns metadata structs with id, timestamps, and custom metadata
    """
    try:
        savefiles = db.query(SaveFile).all()
        
        return [
            {
                "id": sf.id,
                "metadata": sf.file_metadata or {},
                "created_at": sf.created_at.isoformat(),
                "updated_at": sf.updated_at.isoformat(),
                "size": len(sf.compressed_data) if sf.compressed_data else 0
            }
            for sf in savefiles
        ]
    except Exception as e:
        logger.error(f"Error listing savefiles: {e}")
        raise HTTPException(status_code=500, detail="Failed to list savefiles")


@router.post("")
async def upload_savefile(
    file: UploadFile = File(...),
    metadata: str = Form(default="{}"),
    id: Optional[str] = Form(None),
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Upload a compressed save file.
    
    - Admin only
    - Optional custom id (falls back to UUID)
    - Expects compressed file blob
    - Requires metadata JSON in form
    """
    # Verify admin
    try:
        payload = await verify_jwt(authorization)
        await require_admin(payload)
    except HTTPException as e:
        raise e
    
    try:
        import json
        metadata_dict = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON")
    
    # Generate or use provided ID
    savefile_id = id or str(uuid.uuid4())
    
    try:
        # Read compressed file data
        file_data = await file.read()
        
        # Check if already exists
        existing = db.query(SaveFile).filter(SaveFile.id == savefile_id).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Save file with id '{savefile_id}' already exists")
        
        # Create new save file
        savefile = SaveFile(
            id=savefile_id,
            compressed_data=file_data,
            metadata=metadata_dict
        )
        db.add(savefile)
        db.commit()
        db.refresh(savefile)
        
        logger.info(f"Uploaded savefile: {savefile_id} ({len(file_data)} bytes compressed)")
        
        return {
            "id": savefile.id,
            "metadata": savefile.file_metadata,
            "created_at": savefile.created_at.isoformat(),
            "size": len(file_data)
        }
    
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Save file ID conflict")
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading savefile: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload savefile")


@router.get("/{savefile_id}")
async def download_savefile(
    savefile_id: str,
    db: Session = Depends(get_db)
):
    """
    Download a compressed save file with metadata.
    
    - Anyone can download
    - Returns compressed blob + metadata
    """
    try:
        savefile = db.query(SaveFile).filter(SaveFile.id == savefile_id).first()
        
        if not savefile:
            raise HTTPException(status_code=404, detail="Save file not found")
        
        return {
            "id": savefile.id,
            "metadata": savefile.file_metadata or {},
            "created_at": savefile.created_at.isoformat(),
            "updated_at": savefile.updated_at.isoformat(),
            "compressed_data": savefile.compressed_data.hex(),  # Return as hex string
            "size": len(savefile.compressed_data)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading savefile {savefile_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to download savefile")


@router.put("/{savefile_id}")
async def update_savefile(
    savefile_id: str,
    file: UploadFile = File(...),
    metadata: str = Form(default=None),
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Replace a save file's data and/or metadata.
    
    - Admin only
    - Updates compressed blob
    - Optionally updates metadata
    """
    # Verify admin
    try:
        payload = await verify_jwt(authorization)
        await require_admin(payload)
    except HTTPException as e:
        raise e
    
    try:
        savefile = db.query(SaveFile).filter(SaveFile.id == savefile_id).first()
        
        if not savefile:
            raise HTTPException(status_code=404, detail="Save file not found")
        
        # Update file data
        file_data = await file.read()
        savefile.compressed_data = file_data
        
        # Update metadata if provided
        if metadata:
            import json
            try:
                savefile.file_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON")
        
        db.commit()
        db.refresh(savefile)
        
        logger.info(f"Updated savefile: {savefile_id} ({len(file_data)} bytes compressed)")
        
        return {
            "id": savefile.id,
            "metadata": savefile.file_metadata,
            "updated_at": savefile.updated_at.isoformat(),
            "size": len(file_data)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating savefile {savefile_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update savefile")


@router.delete("/{savefile_id}")
async def delete_savefile(
    savefile_id: str,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Delete a save file.
    
    - Admin only
    """
    # Verify admin
    try:
        payload = await verify_jwt(authorization)
        await require_admin(payload)
    except HTTPException as e:
        raise e
    
    try:
        savefile = db.query(SaveFile).filter(SaveFile.id == savefile_id).first()
        
        if not savefile:
            raise HTTPException(status_code=404, detail="Save file not found")
        
        db.delete(savefile)
        db.commit()
        
        logger.info(f"Deleted savefile: {savefile_id}")
        
        return {"success": True, "id": savefile_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting savefile {savefile_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete savefile")
