import hashlib,hmac,json,sqlite3,time
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.billing import Billing

PASSWORD='a-long-test-password'
def register(c,email='owner@example.com'):
    r=c.post('/api/auth/register',json={'email':email,'password':PASSWORD,'display_name':'House Maker'})
    assert r.status_code==201,r.text
    assert 'HttpOnly' in r.headers['set-cookie']
    return r.json()

def test_private_projects_sessions_and_persistence(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as owner,TestClient(app) as other:
        assert owner.get('/api/projects').status_code==401
        user=register(owner)
        project=owner.post('/api/projects',json={'name':'My house'}).json();pid=project['id']
        register(other,'other@example.com')
        assert other.get('/api/projects').json()==[]
        for method,path in [('GET',''),('PATCH',''),('DELETE',''),('POST','/generate'),('POST','/duplicate'),('GET','/print'),('GET','/artifacts/project.zip'),('GET','/geometry')]:
            r=other.request(method,'/api/projects/'+pid+path,json={'name':'Stolen'} if method=='PATCH' else None)
            assert r.status_code==404,(method,path,r.text)
        with sqlite3.connect(tmp_path/'studio.sqlite3') as db:
            db.execute("INSERT INTO jobs(id,project_id,status) VALUES('private-job',?,'FAILED')",(pid,))
            stored=db.execute('SELECT password_hash FROM accounts WHERE id=?',(user['id'],)).fetchone()[0]
            assert PASSWORD not in stored
        assert other.get('/api/jobs/private-job').status_code==404
        assert owner.get('/api/jobs/private-job').status_code==200
        for _ in range(2):assert owner.post('/api/projects',json={'name':'More'}).status_code==201
        assert owner.post('/api/projects',json={'name':'Too many'}).status_code==402
        assert owner.post('/api/projects/'+pid+'/duplicate').status_code==402
        assert owner.patch('/api/account',json={'display_name':'Updated'}).json()['display_name']=='Updated'
        assert owner.patch('/api/account',json={'display_name':'Bad'},headers={'Origin':'https://evil.example'}).status_code==403
        token=owner.cookies.get('ppm_session')
        other.cookies.set('ppm_session',token)
        assert owner.post('/api/account/password',json={'current_password':PASSWORD,'new_password':PASSWORD+'2'}).status_code==204
        assert other.get('/api/projects').status_code==401
        assert owner.get('/api/projects').status_code==200
        assert owner.post('/api/auth/logout').status_code==204
        assert owner.get('/api/projects').status_code==401
    with TestClient(create_app(tmp_path)) as owner:
        assert owner.post('/api/auth/login',json={'email':user['email'],'password':PASSWORD}).status_code==401
        assert owner.post('/api/auth/login',json={'email':user['email'],'password':PASSWORD+'2'}).status_code==200
        assert len(owner.get('/api/projects').json())==3
        assert owner.get('/api/account').json()['project_count']==3
        assert owner.get('/api/billing/plan').json()['configured'] is False
        assert owner.post('/api/billing/checkout').status_code==503

def test_legacy_projects_stay_unassigned(tmp_path):
    app=create_app(tmp_path)
    with sqlite3.connect(tmp_path/'studio.sqlite3') as db:
        db.execute("INSERT INTO projects(id,name,preset,revision,status) VALUES('legacy','Existing','cube_100',1,'DRAFT')")
    with TestClient(app) as c:
        register(c)
        assert c.get('/api/projects').json()==[]
        assert c.get('/api/projects/legacy').status_code==404
    with sqlite3.connect(tmp_path/'studio.sqlite3') as db:
        assert db.execute("SELECT owner_id FROM projects WHERE id='legacy'").fetchone()==(None,)

def test_lifetime_requires_verified_matching_payment(tmp_path,monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY','sk_test_fake')
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET','whsec_test')
    monkeypatch.setenv('STRIPE_LIFETIME_PRICE_ID','price_test')
    captured={};calls=[]
    def stripe(self,method,path,**kwargs):
        calls.append(path)
        if path.startswith('prices/'):
            return {'type':'one_time','active':True,'unit_amount':2900,'currency':'usd'}
        captured.update(kwargs['data'])
        return {'id':'cs_test','url':'https://checkout.stripe.com/c/pay/test','expires_at':time.time()+3600}
    monkeypatch.setattr(Billing,'stripe',stripe)
    with TestClient(create_app(tmp_path)) as c:
        user=register(c)
        assert c.post('/api/billing/checkout').status_code==200
        assert c.post('/api/billing/checkout').status_code==200
        assert calls.count('checkout/sessions')==1
        assert c.get('/api/account?checkout=success').json()['user']['plan']=='starter'
        obj={'id':'cs_test','mode':'payment','payment_status':'paid','client_reference_id':user['id'],'amount_total':2900,'currency':'usd','metadata':{'purchase_id':captured['metadata[purchase_id]']},'livemode':False}
        def send(event_id,changes=None,secret='whsec_test',timestamp=None):
            raw=json.dumps({'id':event_id,'type':'checkout.session.completed','data':{'object':{**obj,**(changes or {})}}}).encode()
            t=timestamp or int(time.time());signature=hmac.new(secret.encode(),str(t).encode()+b'.'+raw,hashlib.sha256).hexdigest()
            return c.post('/api/billing/webhook',content=raw,headers={'stripe-signature':f't={t},v1={signature}'})
        assert send('forged',secret='wrong').status_code==400
        assert send('old',timestamp=int(time.time())-600).status_code==400
        assert send('unpaid',{'payment_status':'unpaid'}).status_code==200
        for field,value in [('amount_total',1),('client_reference_id','other'),('currency','eur'),('livemode',True)]:
            assert send('bad-'+field,{field:value}).status_code==400
        assert c.get('/api/account').json()['user']['plan']=='starter'
        assert send('paid').status_code==200
        assert send('paid').status_code==200
        assert c.get('/api/account').json()['user']['plan']=='lifetime'
        assert c.get('/api/account').json()['project_limit'] is None
        assert c.post('/api/billing/checkout').status_code==409
        assert c.get('/api/billing/purchases').json()[0]['status']=='paid'
        for _ in range(4):assert c.post('/api/projects',json={'name':'Lifetime house'}).status_code==201
