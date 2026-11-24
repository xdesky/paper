"""Account sessions and per-user storage. No credentials or card details reach the client."""
from contextvars import ContextVar
from collections import defaultdict,deque
import hashlib,hmac,json,os,re,secrets,sqlite3,time,threading
from urllib.parse import urlsplit
from fastapi import HTTPException,Request,Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field,ConfigDict,field_validator

CURRENT_USER=ContextVar('account_id',default=None)
COOKIE='ppm_session'
TTL=60*60*24*14

def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    value=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=64).hex()
    return salt+'$'+value

def password_matches(password,stored):
    try:return hmac.compare_digest(password_hash(password,stored.split('$')[0]),stored)
    except (ValueError,TypeError):return False

class Credentials(BaseModel):
    model_config=ConfigDict(extra='forbid')
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=10,max_length=128)
    @field_validator('email')
    @classmethod
    def email_address(cls,value):
        value=value.strip().lower()
        if value=='admin':return 'admin@printplaymagic.local'
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError('Enter a valid email address.')
        return value
class Registration(Credentials):
    display_name:str=Field(min_length=1,max_length=80)
    @field_validator('email')
    @classmethod
    def registration_email(cls,value):
        if '@' not in value:raise ValueError('Enter a valid email address.')
        return value
class Profile(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    display_name:str=Field(min_length=1,max_length=80)
class PasswordChange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    current_password:str=Field(min_length=1,max_length=128)
    new_password:str=Field(min_length=10,max_length=128)

class AdminAccountUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    active:bool
    lifetime:bool

class Accounts:
    def __init__(self,connection):
        self.connection=connection
        self.base_url=os.getenv('PPM_PUBLIC_URL','http://127.0.0.1:8000').rstrip('/')
        parsed=urlsplit(self.base_url)
        if parsed.scheme not in ('http','https') or not parsed.netloc:raise ValueError('Invalid PPM_PUBLIC_URL')
        if parsed.scheme!='https' and parsed.hostname not in ('localhost','127.0.0.1','::1'):raise ValueError('Public deployments require HTTPS')
        self.secure=parsed.scheme=='https'
        self.free_limit=int(os.getenv('PPM_FREE_PROJECT_LIMIT','3'))
        self.attempts=defaultdict(deque);self.lock=threading.Lock()
        with connection() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,display_name TEXT NOT NULL,password_hash TEXT NOT NULL,lifetime INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,account_id TEXT NOT NULL,expires_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS sessions_account ON sessions(account_id);
            ''')
            account_columns={r['name'] for r in db.execute('PRAGMA table_info(accounts)')}
            if 'is_admin' not in account_columns:db.execute('ALTER TABLE accounts ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0')
            if 'is_active' not in account_columns:db.execute('ALTER TABLE accounts ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1')
            # Bootstrap once. The password is stored only as a scrypt hash.
            db.execute('''INSERT OR IGNORE INTO accounts(id,email,display_name,password_hash,lifetime,created_at,is_admin,is_active)
                VALUES(?,?,?,?,0,?,1,1)''',('admin-bootstrap','admin@printplaymagic.local','Admin','b4f0fdd1e9c48665d45dbbb58e7a501a$054ede12bc2dd483480d07a77442e0eaa66fdc0c764ab5171840ba7c657d6af7ce7ccb1006ed011085ed9aaf461bdca9da36aea3c8e3368341bfc6006e2ddd01',time.time()))
            if 'owner_id' not in {r['name'] for r in db.execute('PRAGMA table_info(projects)')}:
                db.execute('ALTER TABLE projects ADD COLUMN owner_id TEXT')
            db.execute('CREATE INDEX IF NOT EXISTS projects_owner ON projects(owner_id)')
    def rate_limit(self,request):
        key=request.client.host if request.client else 'unknown';now=time.time()
        with self.lock:
            attempts=self.attempts[key]
            while attempts and attempts[0]<now-600:attempts.popleft()
            if len(attempts)>=20:raise HTTPException(429,'Too many attempts. Try again in 10 minutes.')
            attempts.append(now)
    def user(self):
        uid=CURRENT_USER.get()
        if not uid:raise HTTPException(401,'Sign in to continue.')
        with self.connection() as db:row=db.execute('SELECT * FROM accounts WHERE id=?',(uid,)).fetchone()
        if not row:raise HTTPException(401,'Sign in to continue.')
        if not row['is_active']:raise HTTPException(403,'This account has been suspended.')
        return row
    def admin(self):
        row=self.user()
        if not row['is_admin']:raise HTTPException(403,'Administrator access is required.')
        return row
    def public_user(self,row):
        return dict(id=row['id'],email=row['email'],display_name=row['display_name'],plan='lifetime' if row['lifetime'] else 'starter',created_at=row['created_at'],is_admin=bool(row['is_admin']),is_active=bool(row['is_active']))
    def check_create(self,db):
        uid=CURRENT_USER.get()
        if not uid:raise HTTPException(401,'Sign in to save your projects.')
        account=db.execute('SELECT lifetime,is_active FROM accounts WHERE id=?',(uid,)).fetchone()
        count=db.execute('SELECT COUNT(*) FROM projects WHERE owner_id=?',(uid,)).fetchone()[0]
        if not account:raise HTTPException(401,'Sign in to continue.')
        if not account['is_active']:raise HTTPException(403,'This account has been suspended.')
        if not account['lifetime'] and count>=self.free_limit:raise HTTPException(402,'Your Starter project library is full. Upgrade to Lifetime or delete a project.')
        return uid
    def session(self,uid,response):
        token=secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE expires_at<?',(time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,time.time()+TTL))
        response.set_cookie(COOKIE,token,max_age=TTL,httponly=True,secure=self.secure,samesite='strict',path='/')
    def install(self,app):
        @app.middleware('http')
        async def account_boundary(request,call_next):
            path=request.url.path
            if request.method not in ('GET','HEAD','OPTIONS') and path.startswith('/api/') and path!='/api/billing/webhook':
                origin=request.headers.get('origin')
                if request.headers.get('sec-fetch-site')=='cross-site' or (origin and origin not in {self.base_url,str(request.base_url).rstrip('/')}):
                    return JSONResponse({'detail':'Cross-site requests are not allowed.'},status_code=403)
            uid=None;raw=request.cookies.get(COOKIE,'')
            if raw:
                with self.connection() as db:
                    row=db.execute('SELECT s.account_id FROM sessions s JOIN accounts a ON a.id=s.account_id WHERE s.token_hash=? AND s.expires_at>? AND a.is_active=1',(hashlib.sha256(raw.encode()).hexdigest(),time.time())).fetchone()
                if row:uid=row['account_id']
            protected=path=='/api/projects' or path.startswith(('/api/projects/','/api/jobs/')) or path=='/api/city/projects' or path.startswith('/api/city/projects/')
            if protected:
                if not uid:return JSONResponse({'detail':'Sign in to access your projects.'},status_code=401)
                parts=path.split('/')
                if path.startswith('/api/city/projects/'):
                    city_id=parts[4] if len(parts)>4 else ''
                    if city_id:
                        with self.connection() as db:
                            row=db.execute('SELECT owner_id FROM city_projects WHERE id=?',(city_id,)).fetchone()
                        if not row or row['owner_id']!=uid:return JSONResponse({'detail':'City project not found.'},status_code=404)
                elif path.startswith(('/api/projects/','/api/jobs/')) and len(parts)>3 and parts[3]:
                    with self.connection() as db:
                        if parts[2]=='jobs':row=db.execute('SELECT p.owner_id FROM jobs j JOIN projects p ON p.id=j.project_id WHERE j.id=?',(parts[3],)).fetchone()
                        else:row=db.execute('SELECT owner_id FROM projects WHERE id=?',(parts[3],)).fetchone()
                    if not row or row['owner_id']!=uid:return JSONResponse({'detail':'Project not found.'},status_code=404)
            token=CURRENT_USER.set(uid)
            try:
                response=await call_next(request)
                if protected or path.startswith(('/api/auth','/api/account','/api/billing')):response.headers['Cache-Control']='no-store'
                return response
            finally:CURRENT_USER.reset(token)
        @app.post('/api/auth/register',status_code=201)
        def register(body:Registration,request:Request,response:Response):
            self.rate_limit(request)
            name=body.display_name.strip()
            if not name:raise HTTPException(422,'Enter your name.')
            uid=secrets.token_hex(16);hashed=password_hash(body.password)
            try:
                with self.connection() as db:db.execute('INSERT INTO accounts(id,email,display_name,password_hash,lifetime,created_at) VALUES(?,?,?,?,0,?)',(uid,body.email,name,hashed,time.time()))
            except sqlite3.IntegrityError:raise HTTPException(409,'An account with this email already exists. Sign in instead.')
            self.session(uid,response)
            with self.connection() as db:row=db.execute('SELECT * FROM accounts WHERE id=?',(uid,)).fetchone()
            return self.public_user(row)
        @app.post('/api/auth/login')
        def login(body:Credentials,request:Request,response:Response):
            self.rate_limit(request)
            with self.connection() as db:row=db.execute('SELECT * FROM accounts WHERE email=?',(body.email,)).fetchone()
            stored=row['password_hash'] if row else password_hash('invalid-account-password',salt='0'*32)
            if not password_matches(body.password,stored) or not row:raise HTTPException(401,'Email or password is incorrect.')
            self.session(row['id'],response);return self.public_user(row)
        @app.post('/api/auth/logout',status_code=204)
        def logout(request:Request,response:Response):
            with self.connection() as db:db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(request.cookies.get(COOKIE,'').encode()).hexdigest(),))
            response.delete_cookie(COOKIE,path='/')
        @app.get('/api/account')
        def account():
            if not CURRENT_USER.get():return {'user':None,'project_limit':self.free_limit,'project_count':0}
            row=self.user()
            with self.connection() as db:count=db.execute('SELECT COUNT(*) FROM projects WHERE owner_id=?',(row['id'],)).fetchone()[0]
            return {'user':self.public_user(row),'project_limit':None if row['lifetime'] else self.free_limit,'project_count':count}
        @app.get('/api/admin/users')
        def admin_users():
            self.admin()
            with self.connection() as db:
                rows=db.execute('''SELECT a.id,a.email,a.display_name,a.lifetime,a.created_at,a.is_admin,a.is_active,
                    COUNT(p.id) AS project_count FROM accounts a LEFT JOIN projects p ON p.owner_id=a.id
                    GROUP BY a.id ORDER BY a.created_at DESC''').fetchall()
            return [dict(id=r['id'],email=r['email'],display_name=r['display_name'],plan='lifetime' if r['lifetime'] else 'starter',created_at=r['created_at'],is_admin=bool(r['is_admin']),is_active=bool(r['is_active']),project_count=r['project_count']) for r in rows]
        @app.patch('/api/admin/users/{account_id}')
        def update_admin_user(account_id:str,body:AdminAccountUpdate):
            self.admin()
            with self.connection() as db:
                target=db.execute('SELECT id,is_admin FROM accounts WHERE id=?',(account_id,)).fetchone()
                if not target:raise HTTPException(404,'User not found.')
                if target['is_admin'] and not body.active:raise HTTPException(400,'Administrator accounts cannot be suspended here.')
                db.execute('UPDATE accounts SET is_active=?,lifetime=? WHERE id=?',(int(body.active),int(body.lifetime),account_id))
                if not body.active:db.execute('DELETE FROM sessions WHERE account_id=?',(account_id,))
                row=db.execute('SELECT a.id,a.email,a.display_name,a.lifetime,a.created_at,a.is_admin,a.is_active,(SELECT COUNT(*) FROM projects p WHERE p.owner_id=a.id) project_count FROM accounts a WHERE id=?',(account_id,)).fetchone()
            return dict(id=row['id'],email=row['email'],display_name=row['display_name'],plan='lifetime' if row['lifetime'] else 'starter',created_at=row['created_at'],is_admin=bool(row['is_admin']),is_active=bool(row['is_active']),project_count=row['project_count'])
        @app.patch('/api/account')
        def profile(body:Profile):
            row=self.user()
            with self.connection() as db:db.execute('UPDATE accounts SET display_name=? WHERE id=?',(body.display_name,row['id']))
            return self.public_user(self.user())
        @app.post('/api/account/password',status_code=204)
        def change_password(body:PasswordChange,request:Request,response:Response):
            self.rate_limit(request)
            row=self.user()
            if not password_matches(body.current_password,row['password_hash']):raise HTTPException(400,'Current password is incorrect.')
            with self.connection() as db:
                db.execute('UPDATE accounts SET password_hash=? WHERE id=?',(password_hash(body.new_password),row['id']))
                db.execute('DELETE FROM sessions WHERE account_id=?',(row['id'],))
            self.session(row['id'],response)
