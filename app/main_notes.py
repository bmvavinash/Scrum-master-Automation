from fastapi import FastAPI, HTTPException, status, Path
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError
from datetime import datetime, timezone
from bson import ObjectId
from app.db import get_notes_collection
from app.schemas import NoteCreate, NoteResponse

app = FastAPI(title='Notes API (FastAPI + MongoDB)')

app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

@app.on_event('startup')
async def startup_indexes():
    coll = get_notes_collection()
    await coll.create_index([('title', ASCENDING), ('created_day', ASCENDING)], unique=True, name='title_createdday_unique')
    await coll.create_index([('created_at', DESCENDING)], name='created_at_desc')

def utc_now():
    return datetime.now(timezone.utc)

@app.post('/api/v1/notes', status_code=status.HTTP_201_CREATED)
async def create_note(payload: NoteCreate):
    coll = get_notes_collection()
    now = utc_now()
    doc = { 'title': payload.title, 'body': payload.body, 'created_at': now, 'updated_at': now, 'created_day': now.date().isoformat() }
    try:
        res = await coll.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail='Note with same title already exists for today')
    except PyMongoError:
        raise HTTPException(status_code=500, detail='database error')
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={'id': str(res.inserted_id)})

@app.get('/api/v1/notes/{id}', response_model=NoteResponse)
async def get_note(id: str = Path(..., description='Mongo ObjectId')):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail='Invalid id')
    coll = get_notes_collection()
    doc = await coll.find_one({'_id': ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail='Note not found')
    return NoteResponse(id=str(doc['_id']), title=doc['title'], body=doc['body'], created_at=doc['created_at'], updated_at=doc['updated_at'])
