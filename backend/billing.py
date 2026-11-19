"""Optional Stripe one-time Checkout. Access is granted only by a signed webhook."""
import hashlib,hmac,json,os,secrets,time
import httpx
from fastapi import HTTPException,Request

class Billing:
    def __init__(self,accounts):
        self.accounts=accounts;self.connection=accounts.connection
        self.key=os.getenv('STRIPE_SECRET_KEY','');self.price_id=os.getenv('STRIPE_LIFETIME_PRICE_ID','');self.secret=os.getenv('STRIPE_WEBHOOK_SECRET','')
        with self.connection() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS purchases(id TEXT PRIMARY KEY,account_id TEXT NOT NULL,session_id TEXT UNIQUE,url TEXT,status TEXT NOT NULL,amount INTEGER NOT NULL,currency TEXT NOT NULL,created_at REAL NOT NULL,expires_at REAL);
            CREATE UNIQUE INDEX IF NOT EXISTS purchases_pending ON purchases(account_id) WHERE status IN ('creating','pending');
            CREATE TABLE IF NOT EXISTS payment_events(id TEXT PRIMARY KEY,processed_at REAL NOT NULL);
            ''')
    @property
    def configured(self):return bool(self.key and self.price_id and self.secret)
    def stripe(self,method,path,**kwargs):
        try:
            response=httpx.request(method,'https://api.stripe.com/v1/'+path,auth=(self.key,''),timeout=20,**kwargs)
            response.raise_for_status();return response.json()
        except (httpx.HTTPError,ValueError):raise HTTPException(502,'The payment provider is unavailable. Please try again.')
    def price(self):
        price=self.stripe('GET','prices/'+self.price_id)
        if price.get('type')!='one_time' or not price.get('active') or not isinstance(price.get('unit_amount'),int) or price['unit_amount']<=0:
            raise HTTPException(503,'The Lifetime price must be an active one-time price.')
        return price
    def install(self,app):
        @app.get('/api/billing/plan')
        def plan():
            result=dict(name='Lifetime',configured=self.configured,mode='test' if self.key.startswith('sk_test_') else 'live' if self.configured else 'unconfigured',one_time=True,free_project_limit=self.accounts.free_limit)
            if self.configured:
                p=self.price();result.update(amount=p['unit_amount'],currency=p['currency'])
            return result
        @app.get('/api/billing/purchases')
        def purchases():
            user=self.accounts.user()
            with self.connection() as db:return [dict(r) for r in db.execute('SELECT id,status,amount,currency,created_at FROM purchases WHERE account_id=? ORDER BY created_at DESC',(user['id'],))]
        @app.post('/api/billing/checkout')
        def checkout():
            user=self.accounts.user()
            if user['lifetime']:raise HTTPException(409,'Your Lifetime access is already active.')
            if not self.configured:raise HTTPException(503,'Purchases are not available yet. Payment setup is pending.')
            price=self.price();purchase_id=secrets.token_hex(16)
            with self.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute("UPDATE purchases SET status='expired' WHERE account_id=? AND status='pending' AND expires_at<?",(user['id'],time.time()))
                existing=db.execute("SELECT * FROM purchases WHERE account_id=? AND status IN ('creating','pending')",(user['id'],)).fetchone()
                if existing:
                    if existing['url']:return {'url':existing['url']}
                    # A retry uses the original idempotency key after a network timeout.
                    purchase_id=existing['id']
                else:db.execute('INSERT INTO purchases VALUES(?,?,NULL,NULL,?,?,?,?,NULL)',(purchase_id,user['id'],'creating',price['unit_amount'],price['currency'],time.time()))
            base=self.accounts.base_url
            session=self.stripe('POST','checkout/sessions',headers={'Idempotency-Key':'lifetime-'+purchase_id},data={
                'mode':'payment','line_items[0][price]':self.price_id,'line_items[0][quantity]':'1',
                'client_reference_id':user['id'],'metadata[purchase_id]':purchase_id,'customer_email':user['email'],
                'success_url':base+'/?checkout=success#account','cancel_url':base+'/?checkout=canceled#account',
            })
            url=session.get('url','')
            if not url.startswith('https://checkout.stripe.com/'):raise HTTPException(502,'The provider returned an invalid checkout URL.')
            with self.connection() as db:db.execute("UPDATE purchases SET session_id=?,url=?,status='pending',expires_at=? WHERE id=? AND status='creating'",(session['id'],url,session.get('expires_at',time.time()+86400),purchase_id))
            return {'url':url}
        @app.post('/api/billing/webhook')
        async def webhook(request:Request):
            if not self.configured:raise HTTPException(503,'Payments are not configured.')
            raw=await request.body()
            if len(raw)>1024*1024:raise HTTPException(413,'Webhook payload is too large.')
            parts=request.headers.get('stripe-signature','').split(',');values={}
            for part in parts:
                key,_,value=part.partition('=');values.setdefault(key,[]).append(value)
            try:timestamp=int(values['t'][0])
            except (KeyError,ValueError):raise HTTPException(400,'Invalid webhook signature.')
            expected=hmac.new(self.secret.encode(),str(timestamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
            if abs(time.time()-timestamp)>300 or not any(hmac.compare_digest(expected,s) for s in values.get('v1',[])):raise HTTPException(400,'Invalid webhook signature.')
            try:event=json.loads(raw);obj=event['data']['object'];event_id=event['id'];kind=event['type']
            except (ValueError,KeyError,TypeError):raise HTTPException(400,'Invalid webhook event.')
            with self.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT 1 FROM payment_events WHERE id=?',(event_id,)).fetchone():return {'received':True}
                if kind in ('checkout.session.completed','checkout.session.async_payment_succeeded') and obj.get('payment_status')=='paid':
                    purchase=db.execute('SELECT * FROM purchases WHERE session_id=?',(obj.get('id'),)).fetchone()
                    if not purchase:raise HTTPException(409,'Checkout is not recorded yet. Retry this event.')
                    matches=obj.get('mode')=='payment' and obj.get('client_reference_id')==purchase['account_id'] and obj.get('amount_total')==purchase['amount'] and obj.get('currency')==purchase['currency'] and obj.get('metadata',{}).get('purchase_id')==purchase['id']
                    if not matches:raise HTTPException(400,'Payment does not match this purchase.')
                    if bool(obj.get('livemode')) != self.key.startswith('sk_live_'):raise HTTPException(400,'Payment mode mismatch.')
                    db.execute('UPDATE accounts SET lifetime=1 WHERE id=?',(purchase['account_id'],))
                    db.execute("UPDATE purchases SET status='paid' WHERE id=?",(purchase['id'],))
                elif kind=='checkout.session.expired':
                    db.execute("UPDATE purchases SET status='expired' WHERE session_id=? AND status='pending'",(obj.get('id'),))
                db.execute('INSERT INTO payment_events VALUES(?,?)',(event_id,time.time()))
            return {'received':True}
