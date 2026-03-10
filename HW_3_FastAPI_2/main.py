import os
import secrets
import string
import hashlib
import json
import pathlib
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import text

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
from jose import JWTError, jwt
import redis.asyncio as redis


SECRET_KEY = os.getenv("SECRET_KEY", "your_super_secret_key_change_this")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shortener.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


CACHE_TTL_REDIRECT = int(os.getenv("CACHE_TTL_REDIRECT", "3600"))
CACHE_TTL_STATS = int(os.getenv("CACHE_TTL_STATS", "300"))
CACHE_TTL_USER = int(os.getenv("CACHE_TTL_USER", "1800"))


app = FastAPI(title="URL Shortener Service with Redis Cache")
security = HTTPBearer()


redis_client: Optional[redis.Redis] = None

@app.on_event("startup")
async def startup_event():
    global redis_client
    try:
        redis_client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        await redis_client.ping()
        print(f"✅ Redis connected: {REDIS_URL}")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")
        print("⚠️ Running without caching (fallback to DB only)")
        redis_client = None

@app.on_event("shutdown")
async def shutdown_event():
    if redis_client:
        await redis_client.close()
        print("✅ Redis connection closed")


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    links = relationship("Link", back_populates="owner")

class Link(Base):
    __tablename__ = "links"
    id = Column(Integer, primary_key=True, index=True)
    short_code = Column(String, unique=True, index=True, nullable=False)
    original_url = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    clicks = Column(Integer, default=0)
    last_accessed_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False)
    
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User", back_populates="links")


if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
Base.metadata.create_all(bind=engine)


class LinkCreate(BaseModel):
    url: HttpUrl
    custom_alias: Optional[str] = None
    expires_in_minutes: Optional[int] = None

class LinkUpdate(BaseModel):
    url: HttpUrl

class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class LinkStats(BaseModel):
    original_url: str
    created_at: datetime
    clicks: int
    last_accessed_at: Optional[datetime]
    expires_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)

class LinkResponse(BaseModel):
    short_code: str
    full_url: str

class LinkInfo(BaseModel):
    short_code: str
    original_url: str
    model_config = ConfigDict(from_attributes=True)

class CleanupResponse(BaseModel):
    message: str
    deleted_count: int

class HealthResponse(BaseModel):
    database: str
    redis: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((salt + password).encode('utf-8'))
    return f"{salt}${hash_obj.hexdigest()}"

def verify_password(plain_password: str, stored_hash: str) -> bool:
    try:
        salt, hash_value = stored_hash.split('$')
        hash_obj = hashlib.sha256((salt + plain_password).encode('utf-8'))
        return hash_obj.hexdigest() == hash_value
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

def cache_key_redirect(short_code: str) -> str:
    return f"redirect:{short_code}"

def cache_key_stats(short_code: str) -> str:
    return f"stats:{short_code}"

def cache_key_user(username: str) -> str:
    return f"user:{username}"

async def invalidate_link_cache(short_code: str):
    """Удаление кэша для конкретной ссылки"""
    if redis_client:
        await redis_client.delete(
            cache_key_redirect(short_code),
            cache_key_stats(short_code)
        )

async def cache_redirect(short_code: str, original_url: str, expires_at: Optional[datetime]):
    """Кэширование данных для редиректа"""
    if not redis_client:
        return
    data = {
        "original_url": original_url,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "is_deleted": False
    }
    await redis_client.setex(
        cache_key_redirect(short_code),
        CACHE_TTL_REDIRECT,
        json.dumps(data)
    )

async def get_cached_redirect(short_code: str) -> Optional[dict]:
    """Получение данных редиректа из кэша"""
    if not redis_client:
        return None
    cached = await redis_client.get(cache_key_redirect(short_code))
    if cached:
        return json.loads(cached)
    return None

async def cache_stats(short_code: str, stats_data: dict):
    """Кэширование статистики"""
    if not redis_client:
        return
    cache_data = {}
    for k, v in stats_data.items():
        if isinstance(v, datetime):
            cache_data[k] = v.isoformat()
        else:
            cache_data[k] = v
    await redis_client.setex(
        cache_key_stats(short_code),
        CACHE_TTL_STATS,
        json.dumps(cache_data)
    )

async def get_cached_stats(short_code: str) -> Optional[dict]:
    """Получение статистики из кэша"""
    if not redis_client:
        return None
    cached = await redis_client.get(cache_key_stats(short_code))
    if cached:
        return json.loads(cached)
    return None

@app.post("/register", response_model=UserResponse)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pw = hash_password(user_data.password)
    new_user = User(username=user_data.username, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    if redis_client:
        await redis_client.setex(
            cache_key_user(user_data.username),
            CACHE_TTL_USER,
            json.dumps({"id": new_user.id, "username": new_user.username})
        )
    
    return new_user

@app.post("/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/links/shorten", response_model=LinkResponse)
async def shorten_link(link_data: LinkCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    short_code = link_data.custom_alias
    if short_code:
        if db.query(Link).filter(Link.short_code == short_code).first():
            raise HTTPException(status_code=400, detail="Custom alias already exists")
    else:
        while True:
            short_code = generate_short_code()
            if not db.query(Link).filter(Link.short_code == short_code).first():
                break
    
    expires_at = None
    if link_data.expires_in_minutes:
        expires_at = datetime.utcnow() + timedelta(minutes=link_data.expires_in_minutes)

    new_link = Link(
        short_code=short_code,
        original_url=str(link_data.url),
        owner_id=current_user.id,
        expires_at=expires_at
    )
    
    db.add(new_link)
    db.commit()
    db.refresh(new_link)
    
    await cache_redirect(short_code, str(link_data.url), expires_at)
    
    return {"short_code": new_link.short_code, "full_url": f"http://localhost:8000/links/{new_link.short_code}"}

@app.get("/links/{short_code}/stats", response_model=LinkStats)
async def get_stats(short_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cached = await get_cached_stats(short_code)
    if cached:
        result = {}
        for k, v in cached.items():
            if k in ["created_at", "last_accessed_at", "expires_at"] and v:
                result[k] = datetime.fromisoformat(v)
            else:
                result[k] = v
        return result
    
    link = db.query(Link).filter(Link.short_code == short_code).first()
    if not link or link.is_deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    
    if link.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    await cache_stats(short_code, {
        "original_url": link.original_url,
        "created_at": link.created_at,
        "clicks": link.clicks,
        "last_accessed_at": link.last_accessed_at,
        "expires_at": link.expires_at
    })
    
    return link

@app.get("/links/{short_code}")
async def redirect_link(short_code: str, db: Session = Depends(get_db)):
    cached = await get_cached_redirect(short_code)
    if cached and not cached.get("is_deleted"):
        expires_at = cached.get("expires_at")
        if expires_at and datetime.fromisoformat(expires_at) < datetime.utcnow():
            await invalidate_link_cache(short_code)
            raise HTTPException(status_code=410, detail="Link has expired")
        
        db_link = db.query(Link).filter(Link.short_code == short_code).first()
        if db_link:
            db_link.clicks += 1
            db_link.last_accessed_at = datetime.utcnow()
            db.commit()
            await cache_stats(short_code, {
                "original_url": db_link.original_url,
                "created_at": db_link.created_at,
                "clicks": db_link.clicks,
                "last_accessed_at": db_link.last_accessed_at,
                "expires_at": db_link.expires_at
            })
        
        return RedirectResponse(url=cached["original_url"])
    
    # Если нет в кэше — идём в БД
    link = db.query(Link).filter(Link.short_code == short_code).first()
    
    if not link or link.is_deleted:
        raise HTTPException(status_code=404, detail="Link not found")

    if link.expires_at and datetime.utcnow() > link.expires_at:
        await invalidate_link_cache(short_code)
        raise HTTPException(status_code=410, detail="Link has expired")

    link.clicks += 1
    link.last_accessed_at = datetime.utcnow()
    db.commit()
    
    await cache_redirect(short_code, link.original_url, link.expires_at)
    await cache_stats(short_code, {
        "original_url": link.original_url,
        "created_at": link.created_at,
        "clicks": link.clicks,
        "last_accessed_at": link.last_accessed_at,
        "expires_at": link.expires_at
    })

    return RedirectResponse(url=link.original_url)

@app.put("/links/{short_code}")
async def update_link(short_code: str, link_data: LinkUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    link = db.query(Link).filter(Link.short_code == short_code).first()
    if not link or link.is_deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    
    if link.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    link.original_url = str(link_data.url)
    db.commit()
    
    await invalidate_link_cache(short_code)
    await cache_redirect(short_code, str(link_data.url), link.expires_at)
    
    return {"message": "Link updated successfully", "new_url": link.original_url}

@app.delete("/links/{short_code}")
async def delete_link(short_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    link = db.query(Link).filter(Link.short_code == short_code).first()
    if not link or link.is_deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    
    if link.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    link.is_deleted = True
    db.commit()
    
    await invalidate_link_cache(short_code)
    if redis_client:
        await redis_client.setex(
            cache_key_redirect(short_code),
            60,
            json.dumps({"is_deleted": True})
        )
    
    return {"message": "Link deleted"}

@app.get("/links/search", response_model=List[LinkInfo])
def search_links(original_url: str = Query(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    links = db.query(Link).filter(
        Link.owner_id == current_user.id,
        Link.original_url.contains(original_url),
        Link.is_deleted == False
    ).all()
    
    return links


@app.post("/admin/cleanup-unused", response_model=CleanupResponse)
async def cleanup_unused_links(days_inactive: int = 30, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    threshold_date = datetime.utcnow() - timedelta(days=days_inactive)
    
    stale_links = db.query(Link).filter(
        Link.owner_id == current_user.id,
        Link.last_accessed_at < threshold_date,
        Link.is_deleted == False
    ).all()
    
    count = 0
    for link in stale_links:
        link.is_deleted = True
        await invalidate_link_cache(link.short_code)
        count += 1
    
    db.commit()
    return {"message": f"Deleted {count} unused links", "deleted_count": count}

@app.get("/links/history/deleted", response_model=List[LinkInfo])
def get_deleted_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    links = db.query(Link).filter(
        Link.owner_id == current_user.id,
        Link.is_deleted == True
    ).all()
    
    return links


@app.get("/health", response_model=HealthResponse)
async def health_check():
    status = {"database": "unknown", "redis": "unknown"}
    
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {str(e)}"
    
    if redis_client:
        try:
            await redis_client.ping()
            status["redis"] = "ok"
        except Exception as e:
            status["redis"] = f"error: {str(e)}"
    else:
        status["redis"] = "not configured"
    
    return status


@app.get("/")
def root():
    return {
        "message": "URL Shortener Service is running!",
        "docs": "http://localhost:8000/docs",
        "health": "http://localhost:8000/health",
        "endpoints": {
            "register": "POST /register",
            "login": "POST /login",
            "shorten": "POST /links/shorten",
            "redirect": "GET /links/{short_code}",
            "stats": "GET /links/{short_code}/stats"
        }
    }